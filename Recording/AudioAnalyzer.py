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


class AudioAnalyzer:
    """Analyze audio recordings with spectral and temporal features."""
    
    def __init__(self, output_dir="Recording/analysis", append_mode=False):
        """
        Initialize audio analyzer.
        
        Args:
            output_dir: Directory for saving analysis plots and reports
            append_mode: If True, append to existing CSV files instead of overwriting
        """
        # Create output directory with date subdirectory
        date_str = datetime.now().strftime("%Y_%m_%d")
        self.output_dir = Path(output_dir) / date_str
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.append_mode = append_mode
        
        # Analysis parameters
        self.nperseg = 2048  # FFT window size for spectrogram
        self.noverlap = 1536  # Overlap for spectrogram
        self.freq_min = 20  # Minimum frequency to display (Hz)
        self.freq_max = 8000  # Maximum frequency to display (Hz)
        
        print(f"AudioAnalyzer initialized")
        print(f"Output directory: {self.output_dir}")
        print(f"CSV mode: {'APPEND' if self.append_mode else 'OVERWRITE'}")
    
    def load_audio(self, filepath, normalization_factor=None):
        """
        Load audio file.
        
        Args:
            filepath: Path to WAV file
            normalization_factor: Optional normalization factor (max peak from experiment)
            
        Returns:
            Tuple of (sample_rate, audio_data, original_peak)
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
        
        # Apply normalization if factor provided
        if normalization_factor is not None and normalization_factor > 0:
            audio_data = audio_data / normalization_factor
            print(f"Loaded: {filepath.name}")
            print(f"  Sample rate: {sample_rate} Hz")
            print(f"  Duration: {len(audio_data)/sample_rate:.2f} s")
            print(f"  Original peak: {original_peak:.4f}")
            print(f"  Normalized to: {normalization_factor:.4f}")
        else:
            print(f"Loaded: {filepath.name}")
            print(f"  Sample rate: {sample_rate} Hz")
            print(f"  Duration: {len(audio_data)/sample_rate:.2f} s")
            print(f"  Samples: {len(audio_data)}")
        
        return sample_rate, audio_data, original_peak
    
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
    
    def compute_rms_energy(self, audio_data, sample_rate, frame_length=2048, hop_length=512):
        """
        Compute RMS (Root Mean Square) energy over time.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            frame_length: Frame size for RMS computation
            hop_length: Hop size between frames
            
        Returns:
            Tuple of (times, rms_values)
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
        
        return times, rms_values
    
    def detect_onset(self, audio_data, sample_rate, threshold=0.1):
        """
        Detect onset (attack) time of audio signal.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate (Hz)
            threshold: RMS threshold for onset detection (0-1)
            
        Returns:
            Onset time in seconds (or None if not detected)
        """
        # Compute RMS with small hop for better resolution
        times, rms = self.compute_rms_energy(audio_data, sample_rate, 
                                             frame_length=512, hop_length=128)
        
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
        
        # Load audio
        sample_rate, audio_data, original_peak = self.load_audio(filepath, normalization_factor)
        duration = len(audio_data) / sample_rate
        
        # Compute features
        print("Computing spectrogram...")
        f_spec, t_spec, Sxx = self.compute_spectrogram(audio_data, sample_rate)
        
        print("Computing spectral flatness...")
        t_flat, flatness = self.compute_spectral_flatness(audio_data, sample_rate)
        
        print("Computing RMS energy...")
        t_rms, rms = self.compute_rms_energy(audio_data, sample_rate)
        
        print("Detecting onset...")
        onset_time = self.detect_onset(audio_data, sample_rate)
        
        print("Estimating fundamental frequency...")
        f0 = self.compute_fundamental_frequency(audio_data, sample_rate)
        
        # Compute summary statistics
        peak_amplitude = np.max(np.abs(audio_data))
        mean_rms = np.mean(rms)
        mean_flatness = np.mean(flatness)
        
        # Create analysis results
        results = {
            'filename': filepath.name,
            'sample_rate': sample_rate,
            'duration': duration,
            'num_samples': len(audio_data),
            'original_peak_amplitude': float(original_peak),  # Store original peak
            'peak_amplitude': float(peak_amplitude),  # Normalized peak (if applied)
            'normalized': normalization_factor is not None,
            'normalization_factor': float(normalization_factor) if normalization_factor else None,
            'mean_rms': float(mean_rms),
            'mean_spectral_flatness': float(mean_flatness),
            'onset_time': float(onset_time) if onset_time else None,
            'fundamental_frequency': float(f0) if f0 else None,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        print(f"\nAnalysis Summary:")
        if normalization_factor:
            print(f"  Original peak amplitude: {original_peak:.4f}")
            print(f"  Normalized peak amplitude: {peak_amplitude:.4f}")
        else:
            print(f"  Peak amplitude: {peak_amplitude:.4f}")
        print(f"  Mean RMS: {mean_rms:.4f}")
        print(f"  Mean spectral flatness: {mean_flatness:.4f}")
        print(f"  Onset time: {onset_time:.4f} s" if onset_time else "  Onset time: Not detected")
        print(f"  Fundamental freq: {f0:.2f} Hz" if f0 else "  Fundamental freq: Not detected")
        
        # Create visualization
        if save_plot:
            print("\nGenerating plots...")
            self._plot_analysis(
                filepath.stem,
                audio_data, sample_rate,
                f_spec, t_spec, Sxx,
                t_flat, flatness,
                t_rms, rms,
                onset_time, f0,
                normalized=normalization_factor is not None,
                original_peak=original_peak
            )
        
        return results
    
    def _plot_analysis(self, basename, audio_data, sample_rate,
                       f_spec, t_spec, Sxx,
                       t_flat, flatness,
                       t_rms, rms,
                       onset_time, f0,
                       normalized=False,
                       original_peak=None):
        """Create comprehensive analysis plot."""
        
        # Create figure with subplots
        fig = plt.figure(figsize=(14, 10))
        gs = gridspec.GridSpec(4, 1, height_ratios=[1, 1.5, 1, 1], hspace=0.3)
        
        time_axis = np.arange(len(audio_data)) / sample_rate
        
        # 1. Waveform
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(time_axis, audio_data, linewidth=0.5, color='steelblue')
        ax1.set_ylabel('Amplitude')
        
        # Update title to show normalization status
        title = f'Audio Analysis: {basename}'
        if normalized:
            title += f' [NORMALIZED - Original Peak: {original_peak:.4f}]'
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
        ax4.set_ylabel('RMS Energy')
        ax4.set_title('RMS Energy Envelope', fontsize=12)
        ax4.grid(True, alpha=0.3)
        ax4.set_xlim(0, time_axis[-1])
        
        # Add mean line
        mean_rms = np.mean(rms)
        ax4.axhline(mean_rms, color='red', linestyle='--', 
                   label=f'Mean: {mean_rms:.4f}', alpha=0.7)
        ax4.legend(loc='upper right')
        
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
        
        # Find all matching audio files
        audio_files = sorted(audio_dir.glob(pattern))
        
        if not audio_files:
            print(f"No files matching '{pattern}' found in {audio_dir}")
            return []
        
        print(f"\n{'='*60}")
        print(f"BATCH ANALYSIS")
        print(f"Directory: {audio_dir}")
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
        
        # Save batch summary
        if all_results:
            self._save_batch_summary(audio_dir.name, all_results)
        
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
    
    def compare_recordings(self, filepaths, labels=None):
        """
        Create comparative plots for multiple recordings.
        
        Args:
            filepaths: List of audio file paths
            labels: Optional list of labels for each file
        """
        if labels is None:
            labels = [Path(f).stem for f in filepaths]
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        fig.suptitle('Comparative Audio Analysis', fontsize=14, fontweight='bold')
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(filepaths)))
        
        for i, (filepath, label) in enumerate(zip(filepaths, labels)):
            try:
                sample_rate, audio_data = self.load_audio(filepath)
                
                # Waveform
                time_axis = np.arange(len(audio_data)) / sample_rate
                axes[0].plot(time_axis, audio_data, linewidth=0.5, 
                           label=label, color=colors[i], alpha=0.7)
                
                # Spectral flatness
                t_flat, flatness = self.compute_spectral_flatness(audio_data, sample_rate)
                axes[1].plot(t_flat, flatness, linewidth=1.5, 
                           label=label, color=colors[i])
                
                # RMS energy
                t_rms, rms = self.compute_rms_energy(audio_data, sample_rate)
                axes[2].plot(t_rms, rms, linewidth=1.5, 
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
        axes[2].set_ylabel('RMS Energy')
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
    
    # Parse command line arguments for append mode
    append_mode = '--append' in sys.argv or '-a' in sys.argv
    
    # Remove flags from argv to get file/directory arguments
    args = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    
    analyzer = AudioAnalyzer(output_dir="Recording/analysis", append_mode=append_mode)
    
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
                analyzer.analyze_directory(audio_subdir)
            else:
                analyzer.analyze_directory(target_path)
        else:
            print(f"Error: '{target}' is not a valid file or directory")
    
    else:
        # Interactive mode
        print("\nNo arguments provided. Looking for recording sessions...\n")
        
        recordings_dir = Path("Recording/output")
        if recordings_dir.exists():
            # Find all date directories (format: YYYY_MM_DD)
            date_dirs = sorted([d for d in recordings_dir.iterdir() if d.is_dir() and '_' in d.name])
            
            if not date_dirs:
                print("No date directories found in Recording/output/")
                print("\nUsage:")
                print("  python AudioAnalyzer.py <file.wav>              # Analyze single file")
                print("  python AudioAnalyzer.py <directory>             # Analyze all WAV files")
                print("  python AudioAnalyzer.py <directory> --append    # Append to existing CSV")
                print("  python AudioAnalyzer.py <directory> -a          # Short form for append")
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
                                            analyzer.analyze_directory(audio_dir)
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
                                                analyzer.analyze_directory(audio_dir)
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
            print("'Recording/output/' directory not found")
            print("\nUsage:")
            print("  python AudioAnalyzer.py <file.wav>              # Analyze single file")
            print("  python AudioAnalyzer.py <directory>             # Analyze all WAV files")
            print("  python AudioAnalyzer.py <directory> --append    # Append to existing CSV")
            print("  python AudioAnalyzer.py <directory> -a          # Short form for append")
    
    print("\n✓ Analysis complete!")
    print(f"Results saved to: {analyzer.output_dir}")
