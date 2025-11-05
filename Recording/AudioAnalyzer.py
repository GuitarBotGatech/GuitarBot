"""
AudioAnalyzer.py - Audio analysis tool for GuitarBot recordings

Analyzes audio files from recording sessions and provides visualizations:
- Waveform plots
- Spectrograms (STFT)
- Spectral flatness (measure of noise vs. tonality)
- Peak detection and RMS analysis
- Frequency domain analysis

Features:
- Batch processing of audio directories
- Individual file analysis
- Comparative analysis across multiple recordings
- Export plots to PNG files
- Generate analysis reports (JSON/CSV)

Requirements:
- numpy
- scipy
- matplotlib
- librosa (for advanced audio features)
"""

import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime
import json
import csv
import re


class AudioAnalyzer:
    """Analyze audio recordings with spectral and temporal features."""
    
    def __init__(self, output_dir=None, append_mode=False, match_recording_structure=True):
        """
        Initialize audio analyzer.
        
        Args:
            output_dir: Directory for saving analysis plots and reports (defaults to ../GuitarBot_Data/analysis)
            append_mode: If True, append to existing CSV files instead of overwriting
            match_recording_structure: If True, mirror the recording session's date/time structure
        """
        # Default to external data directory (outside repo)
        if output_dir is None:
            # Get repo root (GuitarBot/) and go up one level to GuitarBot_Data/
            repo_root = Path(__file__).parent.parent
            output_dir = repo_root.parent / "GuitarBot_Data" / "analysis"
        
        self.base_output_dir = Path(output_dir)
        self.output_dir = None  # Will be set when analyzing
        self.append_mode = append_mode
        self.match_recording_structure = match_recording_structure
        
        # Analysis parameters
        self.nperseg = 2048  # FFT window size for spectrogram
        self.noverlap = 1536  # Overlap for spectrogram
        self.freq_min = 20  # Minimum frequency to display (Hz)
        self.freq_max = 8000  # Maximum frequency to display (Hz)
        
        print(f"AudioAnalyzer initialized")
        print(f"Base output directory: {self.base_output_dir}")
        print(f"CSV mode: {'APPEND' if self.append_mode else 'OVERWRITE'}")
        print(f"Structure matching: {'ENABLED' if self.match_recording_structure else 'DISABLED'}")
    
    def trim_silence(self, audio_data, sample_rate, threshold_db=-40, frame_length=2048, hop_length=512):
        """
        Trim silence from the beginning of audio signal.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            threshold_db: Threshold in dBFS below which audio is considered silence
            frame_length: Frame size for RMS computation
            hop_length: Hop size between frames
            
        Returns:
            Tuple of (trimmed_audio, trim_start_samples, trim_start_time)
        """
        # Compute RMS energy in dB
        num_frames = 1 + (len(audio_data) - frame_length) // hop_length
        rms_values = np.zeros(num_frames)
        
        for i in range(num_frames):
            start = i * hop_length
            end = start + frame_length
            frame = audio_data[start:end]
            rms_values[i] = np.sqrt(np.mean(frame**2))
        
        # Convert to dBFS
        rms_db = 20 * np.log10(rms_values + 1e-10)
        
        # Find first frame above threshold
        above_threshold = np.where(rms_db > threshold_db)[0]
        
        if len(above_threshold) > 0:
            # Start a bit before the first non-silent frame (for attack transient)
            first_non_silent = above_threshold[0]
            # Go back 5 frames (or to beginning) to capture attack
            trim_frame = max(0, first_non_silent - 5)
            trim_sample = trim_frame * hop_length
            trim_time = trim_sample / sample_rate
            
            trimmed_audio = audio_data[trim_sample:]
            
            return trimmed_audio, trim_sample, trim_time
        else:
            # All silence, return original
            return audio_data, 0, 0.0
    
    def load_audio(self, filepath, normalization_factor=None, trim_silence=True):
        """
        Load audio file.
        
        Args:
            filepath: Path to WAV file
            normalization_factor: Optional normalization factor (max peak from experiment)
            trim_silence: If True, trim silence from beginning (default: True)
            
        Returns:
            Tuple of (sample_rate, audio_data, original_peak, trim_time)
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Audio file not found: {filepath}")
        
        sample_rate, audio_data = wavfile.read(filepath)
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Convert to float if integer
        if audio_data.dtype in [np.int16, np.int32]:
            audio_data = audio_data.astype(np.float32)
            max_val = np.iinfo(np.int16).max if audio_data.dtype == np.int16 else 32768.0
            audio_data = audio_data / max_val
        
        # Store original peak before normalization
        original_peak = np.max(np.abs(audio_data))
        original_duration = len(audio_data) / sample_rate
        
        # Trim silence from beginning
        trim_time = 0.0
        if trim_silence:
            audio_data, trim_samples, trim_time = self.trim_silence(audio_data, sample_rate)
            if trim_samples > 0:
                print(f"Loaded: {filepath.name}")
                print(f"  Sample rate: {sample_rate} Hz")
                print(f"  Original duration: {original_duration:.2f} s")
                print(f"  Trimmed {trim_time:.3f} s of silence from beginning")
                print(f"  Final duration: {len(audio_data)/sample_rate:.2f} s")
        
        # Apply normalization if factor provided
        if normalization_factor is not None and normalization_factor > 0:
            audio_data = audio_data / normalization_factor
            if not trim_silence or trim_samples == 0:
                print(f"Loaded: {filepath.name}")
                print(f"  Sample rate: {sample_rate} Hz")
                print(f"  Duration: {len(audio_data)/sample_rate:.2f} s")
            print(f"  Original peak: {original_peak:.4f}")
            print(f"  Normalized to: {normalization_factor:.4f}")
        else:
            if not trim_silence or trim_samples == 0:
                print(f"Loaded: {filepath.name}")
                print(f"  Sample rate: {sample_rate} Hz")
                print(f"  Duration: {len(audio_data)/sample_rate:.2f} s")
                print(f"  Samples: {len(audio_data)}")
        
        return sample_rate, audio_data, original_peak, trim_time
    
    def compute_spectrogram(self, audio_data, sample_rate):
        """
        Compute spectrogram using Short-Time Fourier Transform (STFT).
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            
        Returns:
            Tuple of (frequencies, times, Sxx) where Sxx is the spectrogram
        """
        f, t, Sxx = signal.spectrogram(
            audio_data,
            fs=sample_rate,
            nperseg=self.nperseg,
            noverlap=self.noverlap,
            window='hann',
            scaling='density'
        )
        
        # Convert to dB scale
        Sxx_db = 10 * np.log10(Sxx + 1e-10)
        
        return f, t, Sxx_db
    
    def compute_spectral_flatness(self, audio_data, sample_rate):
        """
        Compute spectral flatness over time.
        
        Spectral flatness is a measure of how noise-like vs. tone-like a sound is.
        - Value near 0: tone-like (musical note)
        - Value near 1: noise-like
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            
        Returns:
            Tuple of (times, spectral_flatness)
        """
        # Compute STFT
        f, t, Zxx = signal.stft(
            audio_data,
            fs=sample_rate,
            nperseg=self.nperseg,
            noverlap=self.noverlap
        )
        
        # Magnitude spectrum
        mag = np.abs(Zxx)
        
        # Compute spectral flatness for each time frame
        # Flatness = geometric_mean / arithmetic_mean
        eps = 1e-10
        geometric_mean = np.exp(np.mean(np.log(mag + eps), axis=0))
        arithmetic_mean = np.mean(mag, axis=0)
        
        spectral_flatness = geometric_mean / (arithmetic_mean + eps)
        
        return t, spectral_flatness
    
    def compute_rms_energy(self, audio_data, sample_rate, frame_length=2048, hop_length=512, return_db=True):
        """
        Compute RMS (Root Mean Square) energy over time.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            frame_length: Frame size for RMS computation
            hop_length: Hop size between frames
            return_db: If True, return values in dBFS (decibels full scale)
            
        Returns:
            Tuple of (times, rms_values) where rms_values are in dBFS if return_db=True
        """
        # Frame the audio
        num_frames = 1 + (len(audio_data) - frame_length) // hop_length
        rms_values = np.zeros(num_frames)
        times = np.zeros(num_frames)
        
        for i in range(num_frames):
            start = i * hop_length
            end = start + frame_length
            frame = audio_data[start:end]
            rms_values[i] = np.sqrt(np.mean(frame**2))
            times[i] = start / sample_rate
        
        # Convert to dBFS if requested
        if return_db:
            # dBFS = 20 * log10(RMS / 1.0) where 1.0 is full scale
            # Add small epsilon to avoid log(0)
            rms_values = 20 * np.log10(rms_values + 1e-10)
        
        return times, rms_values
    
    def detect_onset(self, audio_data, sample_rate, threshold=0.1):
        """
        Detect onset (attack) time of audio signal.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            threshold: RMS threshold for onset detection (0-1, linear scale)
            
        Returns:
            Onset time in seconds (or None if not detected)
        """
        # Compute RMS with small hop for better resolution (use linear values for threshold)
        times, rms = self.compute_rms_energy(audio_data, sample_rate, 
                                             frame_length=512, hop_length=128,
                                             return_db=False)
        
        # Find first frame above threshold
        onset_idx = np.where(rms > threshold)[0]
        if len(onset_idx) > 0:
            return times[onset_idx[0]]
        return None
    
    def compute_fundamental_frequency(self, audio_data, sample_rate, 
                                     fmin=80, fmax=1000):
        """
        Estimate fundamental frequency using autocorrelation.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            fmin: Minimum frequency to search (Hz)
            fmax: Maximum frequency to search (Hz)
            
        Returns:
            Estimated fundamental frequency (Hz) or None
        """
        # Use middle section of audio for more stable estimate
        start = len(audio_data) // 4
        end = 3 * len(audio_data) // 4
        segment = audio_data[start:end]
        
        # Autocorrelation
        correlation = np.correlate(segment, segment, mode='full')
        correlation = correlation[len(correlation)//2:]
        
        # Find peaks in autocorrelation
        min_lag = int(sample_rate / fmax)
        max_lag = int(sample_rate / fmin)
        
        if max_lag < len(correlation):
            search_region = correlation[min_lag:max_lag]
            if len(search_region) > 0:
                peak_lag = np.argmax(search_region) + min_lag
                f0 = sample_rate / peak_lag
                return f0
        
        return None
    
    def _load_metadata(self, audio_filepath):
        """
        Load metadata JSON file corresponding to an audio file.
        
        Args:
            audio_filepath: Path to the audio file (e.g., "0001_dynamics_note40_param64.wav")
            
        Returns:
            Dictionary with metadata, or None if not found
        """
        audio_filepath = Path(audio_filepath)
        
        # Look for metadata file in parent directory structure
        # Typical structure: session_dir/audio/0001_xxx.wav
        #                   session_dir/metadata/0001_metadata.json
        
        # Extract test number from filename (e.g., "0001" from "0001_dynamics_note40.wav")
        match = re.match(r'^(\d{4})_', audio_filepath.name)
        if not match:
            return None
        
        test_number = match.group(1)
        
        # Look for metadata file
        # Try parent/metadata directory first (RecordingTestSession structure)
        audio_dir = audio_filepath.parent
        session_dir = audio_dir.parent
        metadata_dir = session_dir / "metadata"
        metadata_file = metadata_dir / f"{test_number}_metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                return metadata
            except Exception as e:
                print(f"  Warning: Failed to load metadata from {metadata_file}: {e}")
                return None
        
        return None
    
    def analyze_single_file(self, filepath, save_plot=True, normalization_factor=None):
        """
        Perform complete analysis on a single audio file.
        
        Args:
            filepath: Path to audio file
            save_plot: Whether to save analysis plot
            normalization_factor: Optional normalization factor for experiment consistency
            
        Returns:
            Dictionary with analysis results
        """
        filepath = Path(filepath)
        print(f"\n{'='*60}")
        print(f"Analyzing: {filepath.name}")
        print(f"{'='*60}")
        
        # Load audio (with automatic silence trimming)
        sample_rate, audio_data, original_peak, trim_time = self.load_audio(filepath, normalization_factor)
        duration = len(audio_data) / sample_rate
        
        # Compute features
        print("Computing spectrogram...")
        f_spec, t_spec, Sxx = self.compute_spectrogram(audio_data, sample_rate)
        
        print("Computing spectral flatness...")
        t_flat, flatness = self.compute_spectral_flatness(audio_data, sample_rate)
        
        print("Computing RMS energy...")
        t_rms, rms_db = self.compute_rms_energy(audio_data, sample_rate, return_db=True)
        
        print("Detecting onset...")
        onset_time = self.detect_onset(audio_data, sample_rate)
        
        print("Estimating fundamental frequency...")
        f0 = self.compute_fundamental_frequency(audio_data, sample_rate)
        
        # Load metadata if available (look for corresponding JSON file)
        metadata = self._load_metadata(filepath)
        
        # Compute summary statistics
        peak_amplitude = np.max(np.abs(audio_data))
        mean_rms_db = np.mean(rms_db)
        peak_rms_db = np.max(rms_db)  # Maximum RMS across all frames (loudest moment)
        mean_flatness = np.mean(flatness)
        
        # Create analysis results
        results = {
            'filename': filepath.name,
            'sample_rate': sample_rate,
            'duration': duration,
            'num_samples': len(audio_data),
            'trim_time': float(trim_time),  # Time trimmed from beginning
            'original_peak_amplitude': float(original_peak),  # Store original peak
            'peak_amplitude': float(peak_amplitude),  # Normalized peak (if applied)
            'normalized': normalization_factor is not None,
            'normalization_factor': float(normalization_factor) if normalization_factor else None,
            'mean_rms_db': float(mean_rms_db),  # Mean RMS in dBFS
            'peak_rms_db': float(peak_rms_db),  # Peak RMS in dBFS (loudest moment)
            'mean_spectral_flatness': float(mean_flatness),
            'onset_time': float(onset_time) if onset_time else None,
            'fundamental_frequency': float(f0) if f0 else None,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # Add metadata fields if available (velocity, midi_note, test_type, etc.)
        if metadata:
            # Add relevant metadata fields to results
            metadata_fields = ['velocity', 'midi_note', 'test_type', 'parameter', 
                             'test_number', 'osc_address', 'force_level']
            for field in metadata_fields:
                if field in metadata:
                    results[field] = metadata[field]
        
        print(f"\nAnalysis Summary:")
        if normalization_factor:
            print(f"  Original peak amplitude: {original_peak:.4f}")
            print(f"  Normalized peak amplitude: {peak_amplitude:.4f}")
        else:
            print(f"  Peak amplitude: {peak_amplitude:.4f}")
        print(f"  Mean RMS: {mean_rms_db:.2f} dBFS")
        print(f"  Peak RMS: {peak_rms_db:.2f} dBFS (loudest moment)")
        print(f"  Mean spectral flatness: {mean_flatness:.4f}")
        print(f"  Onset time: {onset_time:.4f} s" if onset_time else "  Onset time: Not detected")
        print(f"  Fundamental freq: {f0:.2f} Hz" if f0 else "  Fundamental freq: Not detected")
        
        # Print metadata if available
        if metadata:
            print(f"\nMetadata:")
            if 'test_type' in metadata:
                print(f"  Test type: {metadata['test_type']}")
            if 'midi_note' in metadata:
                print(f"  MIDI note: {metadata['midi_note']}")
            if 'velocity' in metadata:
                print(f"  Velocity: {metadata['velocity']}")
            if 'force_level' in metadata:
                print(f"  Force level: {metadata['force_level']}")
        
        # Create visualization
        if save_plot:
            print("\nGenerating plots...")
            self._plot_analysis(
                filepath.stem,
                audio_data, sample_rate,
                f_spec, t_spec, Sxx,
                t_flat, flatness,
                t_rms, rms_db,
                onset_time, f0,
                normalized=normalization_factor is not None,
                original_peak=original_peak,
                metadata=metadata,
                trim_time=trim_time
            )
        
        return results
    
    def _plot_analysis(self, basename, audio_data, sample_rate,
                       f_spec, t_spec, Sxx,
                       t_flat, flatness,
                       t_rms, rms,
                       onset_time, f0,
                       normalized=False,
                       original_peak=None,
                       metadata=None,
                       trim_time=0.0):
        """Create comprehensive analysis plot."""
        
        # Create figure with subplots
        fig = plt.figure(figsize=(14, 10))
        gs = gridspec.GridSpec(4, 1, height_ratios=[1, 1.5, 1, 1], hspace=0.3)
        
        time_axis = np.arange(len(audio_data)) / sample_rate
        
        # 1. Waveform
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(time_axis, audio_data, linewidth=0.5, color='steelblue')
        ax1.set_ylabel('Amplitude')
        
        # Update title to show normalization status, trim info, and metadata
        title = f'Audio Analysis: {basename}'
        if trim_time > 0:
            title += f' [TRIMMED: {trim_time:.3f}s removed]'
        if normalized:
            title += f' [NORMALIZED - Original Peak: {original_peak:.4f}]'
        
        # Add metadata to title if available
        if metadata:
            metadata_parts = []
            if 'test_type' in metadata:
                metadata_parts.append(f"Type: {metadata['test_type']}")
            if 'midi_note' in metadata:
                metadata_parts.append(f"Note: {metadata['midi_note']}")
            if 'velocity' in metadata:
                metadata_parts.append(f"Velocity: {metadata['velocity']}")
            if 'force_level' in metadata:
                metadata_parts.append(f"Force: {metadata['force_level']:.2f}")
            
            if metadata_parts:
                title += '\n' + ' | '.join(metadata_parts)
        
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, time_axis[-1])
        
        # Mark onset if detected
        if onset_time is not None:
            ax1.axvline(onset_time, color='red', linestyle='--', 
                       label=f'Onset: {onset_time:.3f}s', alpha=0.7)
            ax1.legend(loc='upper right')
        
        # 2. Spectrogram
        ax2 = fig.add_subplot(gs[1])
        
        # Limit frequency range for better visualization
        freq_mask = (f_spec >= self.freq_min) & (f_spec <= self.freq_max)
        
        pcm = ax2.pcolormesh(t_spec, f_spec[freq_mask], Sxx[freq_mask, :],
                             shading='gouraud', cmap='viridis')
        ax2.set_ylabel('Frequency (Hz)')
        ax2.set_title('Spectrogram (STFT)', fontsize=12)
        cbar = plt.colorbar(pcm, ax=ax2)
        cbar.set_label('Power (dB)')
        
        # Mark fundamental frequency if detected
        if f0 is not None and self.freq_min <= f0 <= self.freq_max:
            ax2.axhline(f0, color='red', linestyle='--', 
                       label=f'F0: {f0:.1f} Hz', alpha=0.7, linewidth=2)
            # Also mark harmonics
            for harmonic in [2, 3, 4]:
                harmonic_freq = f0 * harmonic
                if harmonic_freq <= self.freq_max:
                    ax2.axhline(harmonic_freq, color='orange', linestyle=':', 
                               alpha=0.5, linewidth=1)
            ax2.legend(loc='upper right')
        
        # 3. Spectral Flatness
        ax3 = fig.add_subplot(gs[2])
        ax3.plot(t_flat, flatness, linewidth=1.5, color='green')
        ax3.set_ylabel('Spectral Flatness')
        ax3.set_title('Spectral Flatness (0=tonal, 1=noisy)', fontsize=12)
        ax3.grid(True, alpha=0.3)
        ax3.set_xlim(0, t_spec[-1])
        ax3.set_ylim(0, 1)
        
        # Add mean line
        mean_flat = np.mean(flatness)
        ax3.axhline(mean_flat, color='red', linestyle='--', 
                   label=f'Mean: {mean_flat:.3f}', alpha=0.7)
        ax3.legend(loc='upper right')
        
        # 4. RMS Energy
        ax4 = fig.add_subplot(gs[3])
        ax4.plot(t_rms, rms, linewidth=1.5, color='purple')
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('RMS Energy (dBFS)')
        ax4.set_title('RMS Energy Envelope', fontsize=12)
        ax4.grid(True, alpha=0.3)
        ax4.set_xlim(0, time_axis[-1])
        
        # Add mean and peak lines
        mean_rms = np.mean(rms)
        peak_rms = np.max(rms)
        ax4.axhline(mean_rms, color='red', linestyle='--', 
                   label=f'Mean: {mean_rms:.2f} dBFS', alpha=0.7)
        ax4.axhline(peak_rms, color='orange', linestyle='--', 
                   label=f'Peak: {peak_rms:.2f} dBFS', alpha=0.7, linewidth=2)
        ax4.legend(loc='upper right')
        
        # Add metadata info box if available
        if metadata:
            info_lines = []
            if 'test_type' in metadata:
                info_lines.append(f"Test: {metadata['test_type']}")
            if 'midi_note' in metadata:
                info_lines.append(f"MIDI Note: {metadata['midi_note']}")
            if 'velocity' in metadata:
                info_lines.append(f"Velocity: {metadata['velocity']}")
            if 'force_level' in metadata:
                info_lines.append(f"Force: {metadata['force_level']:.2f}")
            if 'test_number' in metadata:
                info_lines.append(f"Test #: {metadata['test_number']}")
            
            if info_lines:
                info_text = '\n'.join(info_lines)
                # Add text box in lower right corner
                ax4.text(0.98, 0.02, info_text, 
                        transform=ax4.transAxes,
                        fontsize=9,
                        verticalalignment='bottom',
                        horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                        family='monospace')
        
        # Save figure
        plot_filename = self.output_dir / f"{basename}_analysis.png"
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
        print(f"Saved plot: {plot_filename}")
        plt.close()
    
    def find_normalization_factor(self, audio_files):
        """
        Find the maximum peak amplitude across all files for normalization.
        
        Args:
            audio_files: List of audio file paths
            
        Returns:
            Maximum peak amplitude across all files
        """
        max_peak = 0.0
        max_file = None
        
        print("\nScanning files for normalization reference...")
        for audio_file in audio_files:
            try:
                sample_rate, audio_data = wavfile.read(audio_file)
                
                # Convert to mono if stereo
                if len(audio_data.shape) > 1:
                    audio_data = np.mean(audio_data, axis=1)
                
                # Convert to float if integer
                if audio_data.dtype in [np.int16, np.int32]:
                    audio_data = audio_data.astype(np.float32)
                    max_val = np.iinfo(audio_data.dtype).max if audio_data.dtype == np.int16 else 32768.0
                    audio_data = audio_data / max_val
                
                peak = np.max(np.abs(audio_data))
                if peak > max_peak:
                    max_peak = peak
                    max_file = audio_file.name
            except Exception as e:
                print(f"  Warning: Could not read {audio_file.name}: {e}")
        
        if max_peak > 0:
            print(f"  Normalization reference: {max_file} (peak: {max_peak:.4f})")
            print(f"  All files will be normalized to this level\n")
        
        return max_peak
    
    def _setup_output_directory(self, audio_dir):
        """
        Set up output directory, optionally matching recording session structure.
        
        Args:
            audio_dir: Directory being analyzed (e.g., .../recordings/2025_11_04/session_14_30/audio/)
            
        Returns:
            Path to output directory
        """
        if not self.match_recording_structure:
            # Create timestamped directory (old behavior)
            date_str = datetime.now().strftime("%Y_%m_%d")
            time_str = datetime.now().strftime("%H_%M")
            date_time_str = f"{date_str}_{time_str}"
            output_dir = self.base_output_dir / date_time_str
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir
        
        # Try to detect recording session structure
        audio_dir = Path(audio_dir)
        
        # Expected structure: .../recordings/YYYY_MM_DD/session_name_HH_MM/audio/
        # We want to create:     .../analysis/YYYY_MM_DD/session_name_HH_MM/
        
        # Check if this is within a recording session structure
        if audio_dir.name == "audio" and audio_dir.parent.parent.name.count('_') >= 2:
            # Extract date and session name
            session_dir = audio_dir.parent
            date_dir = session_dir.parent
            
            # Create matching structure in analysis directory
            output_dir = self.base_output_dir / date_dir.name / session_dir.name
            output_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"  Matched recording structure:")
            print(f"    Recording: {date_dir.name}/{session_dir.name}")
            print(f"    Analysis:  {date_dir.name}/{session_dir.name}")
            
            return output_dir
        
        # Fallback: create timestamped directory
        print(f"  Warning: Could not detect recording session structure, using timestamp")
        date_str = datetime.now().strftime("%Y_%m_%d")
        time_str = datetime.now().strftime("%H_%M")
        date_time_str = f"{date_str}_{time_str}"
        output_dir = self.base_output_dir / date_time_str
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def analyze_directory(self, audio_dir, pattern="*.wav", save_plots=True, normalize=True):
        """
        Analyze all audio files in a directory.
        
        Args:
            audio_dir: Directory containing audio files
            pattern: File pattern to match (default: "*.wav")
            save_plots: Whether to save individual plots
            normalize: If True, normalize all files to the loudest file in the experiment
            
        Returns:
            List of analysis results for all files
        """
        audio_dir = Path(audio_dir)
        
        if not audio_dir.exists():
            raise FileNotFoundError(f"Directory not found: {audio_dir}")
        
        # Set up output directory (matching recording structure if possible)
        self.output_dir = self._setup_output_directory(audio_dir)
        
        # Find all matching audio files
        audio_files = sorted(audio_dir.glob(pattern))
        
        if not audio_files:
            print(f"No files matching '{pattern}' found in {audio_dir}")
            return []
        
        print(f"\n{'='*60}")
        print(f"BATCH ANALYSIS")
        print(f"Directory: {audio_dir}")
        print(f"Output: {self.output_dir}")
        print(f"Files found: {len(audio_files)}")
        print(f"Normalization: {'ENABLED' if normalize else 'DISABLED'}")
        print(f"{'='*60}\n")
        
        # Find normalization factor if enabled
        norm_factor = None
        if normalize:
            norm_factor = self.find_normalization_factor(audio_files)
            if norm_factor == 0:
                print("Warning: Could not determine normalization factor, proceeding without normalization")
                norm_factor = None
        
        all_results = []
        for audio_file in audio_files:
            try:
                results = self.analyze_single_file(audio_file, save_plot=save_plots, 
                                                  normalization_factor=norm_factor)
                all_results.append(results)
            except Exception as e:
                print(f"Error analyzing {audio_file.name}: {e}")

        # Annotate pick direction for dynamics tests
        if all_results and any('dynamics' in r.get('filename', '').lower() for r in all_results):
            # Group by midi_note
            from collections import defaultdict
            note_groups = defaultdict(list)
            for idx, result in enumerate(all_results):
                midi_note = result.get('midi_note')
                if midi_note is not None:
                    note_groups[midi_note].append((idx, result))
            # For each note, assign pick_direction alternately
            for group in note_groups.values():
                for i, (idx, result) in enumerate(sorted(group, key=lambda x: x[1].get('filename', ''))):
                    pick = 'down' if i % 2 == 0 else 'up'
                    all_results[idx]['pick_direction'] = pick

        # Save batch summary
        if all_results:
            self._save_batch_summary(audio_dir.name, all_results)
            # Analyze pick direction differences if this is a dynamics test
            self._analyze_pick_direction_differences(audio_dir.name, all_results)
        return all_results
    
    def _save_batch_summary(self, session_name, results):
        """Save batch analysis summary to CSV and JSON."""
        
        # CSV export
        csv_file = self.output_dir / f"{session_name}_analysis_summary.csv"
        
        if results:
            keys = results[0].keys()
            file_exists = csv_file.exists()
            
            # Determine write mode
            if self.append_mode and file_exists:
                # Append mode: add new rows to existing file
                with open(csv_file, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writerows(results)
                print(f"\nAppended {len(results)} rows to CSV: {csv_file}")
            else:
                # Overwrite mode or file doesn't exist: write with header
                with open(csv_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(results)
                action = "Overwrote" if file_exists else "Created"
                print(f"\n{action} CSV summary: {csv_file}")
        
        # JSON export - always create a new timestamped file to avoid overwriting
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = self.output_dir / f"{session_name}_analysis_{timestamp}.json"
        summary = {
            'session_name': session_name,
            'total_files': len(results),
            'analysis_timestamp': datetime.now().isoformat(),
            'results': results
        }
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Saved JSON summary: {json_file}")
    
    def _analyze_pick_direction_differences(self, session_name, results):
        """
        Analyze amplitude differences between consecutive picks (down vs up).
        
        Assumes that consecutive recordings of the same MIDI note represent
        alternating pick directions (down, up, down, up...).
        
        Args:
            session_name: Name of the session
            results: List of analysis result dictionaries
        """
        # Try to detect if this is a dynamics test by checking filenames
        has_dynamics = any('dynamics' in r.get('filename', '').lower() for r in results)
        
        if not has_dynamics or len(results) < 2:
            # Not a dynamics test or not enough data
            return
        
        print(f"\n{'='*60}")
        print(f"PICK DIRECTION ANALYSIS (Down vs Up)")
        print(f"{'='*60}\n")
        
        # Group results by MIDI note (extract from filename)
        from collections import defaultdict
        notes_data = defaultdict(list)
        
        for result in results:
            filename = result.get('filename', '')
            # Try to extract note number from filename (e.g., "0001_dynamics_note40_...")
            if 'note' in filename:
                try:
                    note_str = filename.split('note')[1].split('_')[0]
                    midi_note = int(note_str)
                    notes_data[midi_note].append(result)
                except (IndexError, ValueError):
                    continue
        
        if not notes_data:
            print("Could not extract MIDI note information from filenames.")
            return
        
        # Analyze pairs for each note
        pick_comparison_data = []
        
        for midi_note in sorted(notes_data.keys()):
            recordings = notes_data[midi_note]
            
            if len(recordings) < 2:
                continue
            
            print(f"MIDI Note {midi_note}:")
            print(f"  Total recordings: {len(recordings)}")
            
            # Compare consecutive pairs (assuming alternating pick direction)
            for i in range(0, len(recordings) - 1, 2):
                down_pick = recordings[i]
                up_pick = recordings[i + 1] if i + 1 < len(recordings) else None
                
                if up_pick is None:
                    continue
                
                # Extract metrics for comparison
                down_peak_rms = down_pick.get('peak_rms_db', None)
                up_peak_rms = up_pick.get('peak_rms_db', None)
                down_mean_rms = down_pick.get('mean_rms_db', None)
                up_mean_rms = up_pick.get('mean_rms_db', None)
                
                if None in [down_peak_rms, up_peak_rms, down_mean_rms, up_mean_rms]:
                    continue
                
                # Calculate differences
                peak_diff = down_peak_rms - up_peak_rms  # Positive = down is louder
                mean_diff = down_mean_rms - up_mean_rms
                
                pair_num = (i // 2) + 1
                print(f"\n  Pair {pair_num} (Down vs Up):")
                print(f"    Down pick: Peak RMS = {down_peak_rms:.2f} dBFS, Mean RMS = {down_mean_rms:.2f} dBFS")
                print(f"    Up pick:   Peak RMS = {up_peak_rms:.2f} dBFS, Mean RMS = {up_mean_rms:.2f} dBFS")
                print(f"    Difference: Peak = {peak_diff:+.2f} dB, Mean = {mean_diff:+.2f} dB")
                
                if abs(peak_diff) > 3.0:
                    direction = "DOWN" if peak_diff > 0 else "UP"
                    print(f"     Significant bias toward {direction} pick ({abs(peak_diff):.2f} dB)")
                
                # Store for summary
                pick_comparison_data.append({
                    'midi_note': midi_note,
                    'pair': pair_num,
                    'down_peak_rms_db': down_peak_rms,
                    'up_peak_rms_db': up_peak_rms,
                    'down_mean_rms_db': down_mean_rms,
                    'up_mean_rms_db': up_mean_rms,
                    'peak_diff_db': peak_diff,
                    'mean_diff_db': mean_diff
                })
        
        if not pick_comparison_data:
            print("No valid pick pairs found for comparison.")
            return
        
        # Calculate overall statistics
        peak_diffs = [d['peak_diff_db'] for d in pick_comparison_data]
        mean_diffs = [d['mean_diff_db'] for d in pick_comparison_data]
        
        avg_peak_diff = np.mean(peak_diffs)
        std_peak_diff = np.std(peak_diffs)
        avg_mean_diff = np.mean(mean_diffs)
        std_mean_diff = np.std(mean_diffs)
        
        print(f"\n{'='*60}")
        print(f"OVERALL STATISTICS")
        print(f"{'='*60}")
        print(f"Total pairs analyzed: {len(pick_comparison_data)}")
        print(f"\nPeak RMS Difference (Down - Up):")
        print(f"  Average: {avg_peak_diff:+.2f} dB ± {std_peak_diff:.2f} dB")
        print(f"  Range: [{min(peak_diffs):+.2f}, {max(peak_diffs):+.2f}] dB")
        
        print(f"\nMean RMS Difference (Down - Up):")
        print(f"  Average: {avg_mean_diff:+.2f} dB ± {std_mean_diff:.2f} dB")
        print(f"  Range: [{min(mean_diffs):+.2f}, {max(mean_diffs):+.2f}] dB")
        
        # Interpretation
        print(f"\nInterpretation:")
        if abs(avg_peak_diff) < 1.0:
            print(f"  ✓ Excellent balance between pick directions (< 1 dB difference)")
        elif abs(avg_peak_diff) < 3.0:
            print(f"  → Slight bias toward {'DOWN' if avg_peak_diff > 0 else 'UP'} picks ({abs(avg_peak_diff):.2f} dB)")
        else:
            print(f"  ⚠️  Significant bias toward {'DOWN' if avg_peak_diff > 0 else 'UP'} picks ({abs(avg_peak_diff):.2f} dB)")
            print(f"     Consider calibrating picker mechanism or adjusting pick velocities.")
        
        # Save pick comparison data
        self._save_pick_comparison_data(session_name, pick_comparison_data)
        
        # Create visualization
        self._plot_pick_direction_comparison(session_name, pick_comparison_data)
    
    def _save_pick_comparison_data(self, session_name, pick_data):
        """Save pick direction comparison data to CSV."""
        if not pick_data:
            return
        
        csv_file = self.output_dir / f"{session_name}_pick_comparison.csv"
        
        keys = pick_data[0].keys()
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(pick_data)
        
        print(f"\n✓ Pick comparison data saved: {csv_file}")
    
    def _plot_pick_direction_comparison(self, session_name, pick_data):
        """Create visualization of pick direction differences."""
        if not pick_data:
            return
        
        # Convert to arrays
        midi_notes = np.array([d['midi_note'] for d in pick_data])
        pairs = np.array([d['pair'] for d in pick_data])
        peak_diffs = np.array([d['peak_diff_db'] for d in pick_data])
        mean_diffs = np.array([d['mean_diff_db'] for d in pick_data])
        
        # Create figure with multiple subplots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Pick Direction Analysis: Down vs Up', fontsize=14, fontweight='bold')
        
        # 1. Peak RMS differences by note
        ax1 = axes[0, 0]
        unique_notes = sorted(set(midi_notes))
        for note in unique_notes:
            mask = midi_notes == note
            note_peak_diffs = peak_diffs[mask]
            note_pairs = pairs[mask]
            ax1.scatter(note_pairs, note_peak_diffs, s=100, alpha=0.7, label=f'Note {note}')
        
        ax1.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.3)
        ax1.axhline(3, color='red', linestyle='--', linewidth=1, alpha=0.5, label='±3 dB threshold')
        ax1.axhline(-3, color='red', linestyle='--', linewidth=1, alpha=0.5)
        ax1.set_xlabel('Pair Number')
        ax1.set_ylabel('Peak RMS Difference (dB)\n(Down - Up)')
        ax1.set_title('Peak RMS: Down vs Up Pick')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Distribution of peak differences
        ax2 = axes[0, 1]
        ax2.hist(peak_diffs, bins=15, color='steelblue', alpha=0.7, edgecolor='black')
        ax2.axvline(0, color='black', linestyle='-', linewidth=2, label='Perfect balance')
        ax2.axvline(np.mean(peak_diffs), color='red', linestyle='--', linewidth=2, 
                   label=f'Mean: {np.mean(peak_diffs):+.2f} dB')
        ax2.set_xlabel('Peak RMS Difference (dB)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Distribution of Peak RMS Differences')
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')
        
        # 3. Mean RMS differences by note
        ax3 = axes[1, 0]
        for note in unique_notes:
            mask = midi_notes == note
            note_mean_diffs = mean_diffs[mask]
            note_pairs = pairs[mask]
            ax3.scatter(note_pairs, note_mean_diffs, s=100, alpha=0.7, label=f'Note {note}')
        
        ax3.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.3)
        ax3.set_xlabel('Pair Number')
        ax3.set_ylabel('Mean RMS Difference (dB)\n(Down - Up)')
        ax3.set_title('Mean RMS: Down vs Up Pick')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. Box plot comparison
        ax4 = axes[1, 1]
        box_data = [peak_diffs, mean_diffs]
        bp = ax4.boxplot(box_data, labels=['Peak RMS Diff', 'Mean RMS Diff'],
                        patch_artist=True, widths=0.6)
        
        # Color the boxes
        colors = ['steelblue', 'lightcoral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax4.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
        ax4.axhline(3, color='red', linestyle='--', linewidth=1, alpha=0.3)
        ax4.axhline(-3, color='red', linestyle='--', linewidth=1, alpha=0.3)
        ax4.set_ylabel('Amplitude Difference (dB)\n(Down - Up)')
        ax4.set_title('Pick Direction Bias Summary')
        ax4.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        # Save figure
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plot_file = self.output_dir / f"{session_name}_pick_comparison_{timestamp}.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"✓ Pick comparison plot saved: {plot_file}")
        plt.close()
    
    def compare_recordings(self, filepaths, labels=None):
        """
        Create comparative plots for multiple recordings.
        
        Args:
            filepaths: List of audio file paths
            labels: Optional list of labels for each file
        """
        if labels is None:
            labels = []
            for f in filepaths:
                # Try to load metadata to create informative labels
                filepath = Path(f)
                metadata = self._load_metadata(filepath)
                if metadata and 'velocity' in metadata:
                    label = f"{filepath.stem} (vel:{metadata['velocity']})"
                elif metadata and 'midi_note' in metadata:
                    label = f"{filepath.stem} (note:{metadata['midi_note']})"
                else:
                    label = filepath.stem
                labels.append(label)
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        fig.suptitle('Comparative Audio Analysis', fontsize=14, fontweight='bold')
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(filepaths)))
        
        for i, (filepath, label) in enumerate(zip(filepaths, labels)):
            try:
                sample_rate, audio_data, _, _ = self.load_audio(filepath)
                
                # Waveform
                time_axis = np.arange(len(audio_data)) / sample_rate
                axes[0].plot(time_axis, audio_data, linewidth=0.5, 
                           label=label, color=colors[i], alpha=0.7)
                
                # Spectral flatness
                t_flat, flatness = self.compute_spectral_flatness(audio_data, sample_rate)
                axes[1].plot(t_flat, flatness, linewidth=1.5, 
                           label=label, color=colors[i])
                
                # RMS energy (in dBFS)
                t_rms, rms_db = self.compute_rms_energy(audio_data, sample_rate, return_db=True)
                axes[2].plot(t_rms, rms_db, linewidth=1.5, 
                           label=label, color=colors[i])
                
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
        
        axes[0].set_ylabel('Amplitude')
        axes[0].set_title('Waveforms')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        axes[1].set_ylabel('Spectral Flatness')
        axes[1].set_title('Spectral Flatness')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        axes[2].set_xlabel('Time (s)')
        axes[2].set_ylabel('RMS Energy (dBFS)')
        axes[2].set_title('RMS Energy')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save comparison plot
        comparison_file = self.output_dir / f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(comparison_file, dpi=150, bbox_inches='tight')
        print(f"\nSaved comparison plot: {comparison_file}")
        plt.close()


# Example usage and CLI
if __name__ == "__main__":
    import sys
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         GuitarBot Audio Analyzer                              ║
║         Spectrogram, Waveform, Spectral Flatness Analysis     ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    # Parse command line arguments
    append_mode = '--append' in sys.argv or '-a' in sys.argv
    no_normalize = '--no-normalize' in sys.argv or '-n' in sys.argv
    no_match_structure = '--no-match-structure' in sys.argv
    
    # Remove flags from argv to get file/directory arguments
    args = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    
    analyzer = AudioAnalyzer(append_mode=append_mode, match_recording_structure=not no_match_structure)
    
    if len(args) > 0:
        target = args[0]
        target_path = Path(target)
        
        if target_path.is_file():
            # Analyze single file
            print(f"\nAnalyzing single file: {target}")
            analyzer.analyze_single_file(target_path)
            
        elif target_path.is_dir():
            # Analyze directory
            print(f"\nAnalyzing directory: {target}")
            
            # Check for audio subdirectory (from RecordingTestSession structure)
            audio_subdir = target_path / "output"
            if audio_subdir.exists():
                print(f"Found audio subdirectory, analyzing: {audio_subdir}")
                analyzer.analyze_directory(audio_subdir, normalize=not no_normalize)
            else:
                analyzer.analyze_directory(target_path, normalize=not no_normalize)
        else:
            print(f"Error: '{target}' is not a valid file or directory")
    
    else:
        # Interactive mode
        print("\nNo arguments provided. Looking for recording sessions...\n")
        
        # Look in external data directory
        repo_root = Path(__file__).parent.parent
        recordings_dir = repo_root.parent / "GuitarBot_Data" / "recordings"
        if recordings_dir.exists():
            # Find all date directories (format: YYYY_MM_DD)
            date_dirs = sorted([d for d in recordings_dir.iterdir() if d.is_dir() and '_' in d.name])
            
            if not date_dirs:
                print(f"No date directories found in {recordings_dir}/")
                print("\nUsage:")
                print("  python AudioAnalyzer.py <file.wav>                    # Analyze single file")
                print("  python AudioAnalyzer.py <directory>                   # Analyze all WAV files")
                print("  python AudioAnalyzer.py <directory> --append          # Append to existing CSV")
                print("  python AudioAnalyzer.py <directory> -a                # Short form for append")
                print("  python AudioAnalyzer.py <directory> --no-normalize    # Skip normalization")
                print("  python AudioAnalyzer.py <directory> --no-match-structure  # Use timestamped dirs")
            else:
                # Display available dates
                print("Available recording dates:")
                for i, date_dir in enumerate(date_dirs, 1):
                    # Count sessions in this date
                    sessions_in_date = [s for s in date_dir.iterdir() if s.is_dir()]
                    num_sessions = len(sessions_in_date)
                    
                    # Count total audio files
                    total_files = 0
                    for session in sessions_in_date:
                        audio_dir = session / "audio"
                        if audio_dir.exists():
                            total_files += len(list(audio_dir.glob("*.wav")))
                    
                    print(f"  {i}. {date_dir.name} ({num_sessions} sessions, {total_files} files)")
                
                date_choice = input("\nEnter date number (or 'q' to quit): ").strip()
                
                if date_choice.lower() == 'q':
                    pass
                else:
                    try:
                        date_idx = int(date_choice) - 1
                        if 0 <= date_idx < len(date_dirs):
                            selected_date_dir = date_dirs[date_idx]
                            
                            # List sessions in selected date
                            sessions = sorted([s for s in selected_date_dir.iterdir() if s.is_dir()])
                            
                            if not sessions:
                                print(f"No sessions found in {selected_date_dir.name}")
                            else:
                                print(f"\n{'='*60}")
                                print(f"Sessions in {selected_date_dir.name}:")
                                print(f"{'='*60}")
                                print("  0. ALL SESSIONS (analyze all)")
                                
                                for i, session in enumerate(sessions, 1):
                                    audio_dir = session / "audio"
                                    if audio_dir.exists():
                                        num_files = len(list(audio_dir.glob("*.wav")))
                                        print(f"  {i}. {session.name} ({num_files} files)")
                                    else:
                                        print(f"  {i}. {session.name} (no audio)")
                                
                                session_choice = input("\nEnter session number (0 for all, or 'q' to quit): ").strip()
                                
                                if session_choice.lower() == 'q':
                                    pass
                                elif session_choice == '0':
                                    # Analyze all sessions in this date
                                    print(f"\n{'='*60}")
                                    print(f"ANALYZING ALL SESSIONS IN {selected_date_dir.name}")
                                    print(f"{'='*60}\n")
                                    
                                    for session in sessions:
                                        audio_dir = session / "audio"
                                        if audio_dir.exists():
                                            print(f"\n--- Analyzing session: {session.name} ---")
                                            analyzer.analyze_directory(audio_dir, normalize=not no_normalize)
                                        else:
                                            print(f"\nSkipping {session.name} (no audio directory)")
                                    
                                    print(f"\n{'='*60}")
                                    print(f"COMPLETED ALL SESSIONS")
                                    print(f"{'='*60}")
                                else:
                                    try:
                                        session_idx = int(session_choice) - 1
                                        if 0 <= session_idx < len(sessions):
                                            selected_session = sessions[session_idx]
                                            audio_dir = selected_session / "audio"
                                            
                                            if audio_dir.exists():
                                                analyzer.analyze_directory(audio_dir, normalize=not no_normalize)
                                            else:
                                                print(f"No audio directory found in {selected_session}")
                                        else:
                                            print("Invalid session number")
                                    except ValueError:
                                        print("Please enter a valid number")
                        else:
                            print("Invalid date number")
                    except ValueError:
                        print("Please enter a valid number")
        else:
            print(f"Directory not found: {recordings_dir}")
            print("Run RecordingTestSession.py first to create recordings.")
            print("\nUsage:")
            print("  python AudioAnalyzer.py <file.wav>                  # Analyze single file")
            print("  python AudioAnalyzer.py <directory>                 # Analyze all WAV files (normalized)")
            print("  python AudioAnalyzer.py <directory> --append        # Append to existing CSV")
            print("  python AudioAnalyzer.py <directory> -a              # Short form for append")
            print("  python AudioAnalyzer.py <directory> --no-normalize  # Disable normalization")
            print("  python AudioAnalyzer.py <directory> -n              # Short form for no-normalize")
    
    print("\n✓ Analysis complete!")
    print(f"Results saved to: {analyzer.output_dir}")
