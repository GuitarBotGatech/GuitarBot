"""
CrossAnalysis.py - Statistical analysis merging recording metadata with audio analysis

Merges recording session metadata (parameters, test conditions) with audio analysis results
(spectral features, RMS, etc.) to find optimal parameters for GuitarBot performance.

Features:
- Merge metadata CSV with audio analysis CSV
- Statistical analysis per parameter/test type
- Optimization: find best parameters based on quality metrics
- Correlation analysis between parameters and audio features
- Visualization of parameter sweeps
- ML-ready dataset export

Use cases:
- Reinforcement learning reward function design
- Parameter optimization (fretting force, pluck velocity, etc.)
- Quality assessment and anomaly detection
- Performance benchmarking across sessions

Requirements:
- pandas
- numpy
- matplotlib
- scipy (for statistics)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from datetime import datetime
import json
from scipy import stats


class CrossAnalyzer:
    """Cross-analyze recording metadata with audio analysis results."""
    
    def __init__(self, output_dir="Recording/cross_analysis"):
        """
        Initialize cross analyzer.
        
        Args:
            output_dir: Directory for saving cross-analysis results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.merged_data = None
        
        print(f"CrossAnalyzer initialized")
        print(f"Output directory: {self.output_dir}")
    
    def load_and_merge(self, metadata_csv, analysis_csv):
        """
        Load and merge metadata CSV with audio analysis CSV.
        
        Args:
            metadata_csv: Path to session metadata CSV (from RecordingTestSession)
            analysis_csv: Path to audio analysis summary CSV (from AudioAnalyzer)
            
        Returns:
            Merged pandas DataFrame
        """
        print(f"\n{'='*60}")
        print(f"LOADING AND MERGING DATA")
        print(f"{'='*60}")
        
        # Load CSVs
        print(f"Loading metadata: {metadata_csv}")
        metadata_df = pd.read_csv(metadata_csv)
        print(f"  Rows: {len(metadata_df)}")
        
        print(f"Loading analysis: {analysis_csv}")
        analysis_df = pd.read_csv(analysis_csv)
        print(f"  Rows: {len(analysis_df)}")
        
        # Merge on filename (audio_file in metadata, filename in analysis)
        print("\nMerging datasets on filename...")
        merged = pd.merge(
            metadata_df,
            analysis_df,
            left_on='audio_file',
            right_on='filename',
            how='inner',
            suffixes=('_meta', '_audio')
        )
        
        print(f"Merged rows: {len(merged)}")
        
        if len(merged) == 0:
            print("\nWARNING: No matching records found. Check that:")
            print("  1. audio_file column exists in metadata CSV")
            print("  2. filename column exists in analysis CSV")
            print("  3. Filenames match between the two datasets")
            return None
        
        # Add derived columns
        merged = self._add_derived_features(merged)
        
        self.merged_data = merged
        
        print(f"\nMerged columns: {list(merged.columns)}")
        print(f"Test types: {merged['test_type'].unique() if 'test_type' in merged.columns else 'N/A'}")
        
        return merged
    
    def _add_derived_features(self, df):
        """Add derived features useful for analysis."""
        
        # Signal-to-noise ratio (inverse of spectral flatness)
        # Lower flatness = more tonal = better SNR
        if 'mean_spectral_flatness' in df.columns:
            df['snr_estimate'] = 1.0 - df['mean_spectral_flatness']
        
        # Dynamic range (peak to RMS ratio in dB)
        if 'peak_amplitude' in df.columns and 'mean_rms' in df.columns:
            df['dynamic_range_db'] = 20 * np.log10(
                (df['peak_amplitude'] + 1e-10) / (df['mean_rms'] + 1e-10)
            )
        
        # Quality score (composite metric)
        # Higher is better: high SNR, high RMS (not too quiet), reasonable dynamic range
        if all(col in df.columns for col in ['snr_estimate', 'mean_rms', 'dynamic_range_db']):
            # Normalize components to 0-1 range
            snr_norm = (df['snr_estimate'] - df['snr_estimate'].min()) / (df['snr_estimate'].max() - df['snr_estimate'].min() + 1e-10)
            rms_norm = (df['mean_rms'] - df['mean_rms'].min()) / (df['mean_rms'].max() - df['mean_rms'].min() + 1e-10)
            # Penalize extreme dynamic ranges (too compressed or too sparse)
            dr_penalty = np.abs(df['dynamic_range_db'] - df['dynamic_range_db'].median()) / (df['dynamic_range_db'].std() + 1e-10)
            
            df['quality_score'] = (
                0.5 * snr_norm +        # 50% weight on tonality
                0.3 * rms_norm +        # 30% weight on loudness
                0.2 * (1 - dr_penalty)  # 20% weight on reasonable dynamic range
            )
        
        # Pitch accuracy (if fundamental_frequency and midi_note available)
        if 'fundamental_frequency' in df.columns and 'midi_note' in df.columns:
            # Expected frequency from MIDI note: f = 440 * 2^((n-69)/12)
            df['expected_frequency'] = 440.0 * np.power(2.0, (df['midi_note'] - 69) / 12.0)
            df['pitch_error_cents'] = 1200 * np.log2(
                (df['fundamental_frequency'] + 1e-10) / (df['expected_frequency'] + 1e-10)
            )
            df['pitch_error_hz'] = df['fundamental_frequency'] - df['expected_frequency']
        
        return df
    
    def analyze_by_test_type(self, test_type=None):
        """
        Perform statistical analysis grouped by test type.
        
        Args:
            test_type: Specific test type to analyze (None for all)
            
        Returns:
            Dictionary with statistics for each test type
        """
        if self.merged_data is None:
            print("ERROR: No merged data. Run load_and_merge() first.")
            return None
        
        df = self.merged_data
        
        if test_type:
            df = df[df['test_type'] == test_type]
            if len(df) == 0:
                print(f"No data found for test_type '{test_type}'")
                return None
        
        print(f"\n{'='*60}")
        print(f"STATISTICAL ANALYSIS BY TEST TYPE")
        print(f"{'='*60}\n")
        
        results = {}
        
        for ttype in df['test_type'].unique():
            subset = df[df['test_type'] == ttype]
            
            print(f"Test Type: {ttype}")
            print(f"  N = {len(subset)}")
            
            stats_dict = {
                'test_type': ttype,
                'count': len(subset),
                'statistics': {}
            }
            
            # Compute statistics for key metrics
            metrics = [
                'peak_amplitude', 'mean_rms', 'mean_spectral_flatness',
                'snr_estimate', 'dynamic_range_db', 'quality_score',
                'fundamental_frequency', 'pitch_error_cents'
            ]
            
            for metric in metrics:
                if metric in subset.columns:
                    values = subset[metric].dropna()
                    if len(values) > 0:
                        stats_dict['statistics'][metric] = {
                            'mean': float(values.mean()),
                            'std': float(values.std()),
                            'min': float(values.min()),
                            'max': float(values.max()),
                            'median': float(values.median())
                        }
                        
                        print(f"  {metric}:")
                        print(f"    Mean: {values.mean():.4f} ± {values.std():.4f}")
                        print(f"    Range: [{values.min():.4f}, {values.max():.4f}]")
            
            results[ttype] = stats_dict
            print()
        
        return results
    
    def find_optimal_parameters(self, test_type, param_column, metric='quality_score'):
        """
        Find optimal parameter values based on a quality metric.
        
        Args:
            test_type: Test type to analyze (e.g., 'fretting_force')
            param_column: Column containing parameter values (e.g., 'force_level')
            metric: Quality metric to optimize (default: 'quality_score')
            
        Returns:
            DataFrame with parameters sorted by metric
        """
        if self.merged_data is None:
            print("ERROR: No merged data. Run load_and_merge() first.")
            return None
        
        df = self.merged_data
        
        # Filter by test type
        subset = df[df['test_type'] == test_type].copy()
        
        if len(subset) == 0:
            print(f"No data found for test_type '{test_type}'")
            return None
        
        if param_column not in subset.columns:
            print(f"Parameter column '{param_column}' not found")
            print(f"Available columns: {list(subset.columns)}")
            return None
        
        if metric not in subset.columns:
            print(f"Metric '{metric}' not found")
            print(f"Available metrics: {list(subset.columns)}")
            return None
        
        print(f"\n{'='*60}")
        print(f"PARAMETER OPTIMIZATION")
        print(f"Test Type: {test_type}")
        print(f"Parameter: {param_column}")
        print(f"Metric: {metric}")
        print(f"{'='*60}\n")
        
        # Group by parameter and compute statistics
        grouped = subset.groupby(param_column).agg({
            metric: ['mean', 'std', 'count'],
            'mean_rms': 'mean',
            'mean_spectral_flatness': 'mean',
            'peak_amplitude': 'mean'
        }).reset_index()
        
        # Flatten column names
        grouped.columns = ['_'.join(col).strip('_') if col[1] else col[0] 
                          for col in grouped.columns.values]
        
        # Sort by metric (descending = better)
        grouped = grouped.sort_values(f'{metric}_mean', ascending=False)
        
        print("Parameter Ranking (best to worst):")
        print(grouped.to_string(index=False))
        
        # Find optimal parameter
        best_idx = grouped.iloc[0]
        optimal_param = best_idx[param_column]
        optimal_score = best_idx[f'{metric}_mean']
        
        print(f"\n✓ OPTIMAL PARAMETER: {param_column} = {optimal_param}")
        print(f"  {metric} = {optimal_score:.4f}")
        
        return grouped
    
    def correlation_analysis(self, test_type=None):
        """
        Compute correlation matrix between parameters and audio features.
        
        Args:
            test_type: Optional test type filter
            
        Returns:
            Correlation matrix DataFrame
        """
        if self.merged_data is None:
            print("ERROR: No merged data. Run load_and_merge() first.")
            return None
        
        df = self.merged_data
        
        if test_type:
            df = df[df['test_type'] == test_type]
        
        # Select numerical columns for correlation
        numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Remove irrelevant columns
        exclude = ['test_number', 'sample_rate', 'num_samples', 
                  'osc_timestamp', 'recording_duration']
        numerical_cols = [col for col in numerical_cols if col not in exclude]
        
        corr_matrix = df[numerical_cols].corr()
        
        print(f"\n{'='*60}")
        print(f"CORRELATION ANALYSIS")
        if test_type:
            print(f"Test Type: {test_type}")
        print(f"{'='*60}\n")
        
        # Find strong correlations with quality metrics
        quality_metrics = ['quality_score', 'snr_estimate', 'mean_rms']
        
        for metric in quality_metrics:
            if metric in corr_matrix.columns:
                print(f"\nCorrelations with {metric}:")
                corr_series = corr_matrix[metric].sort_values(ascending=False)
                for col, corr_val in corr_series.items():
                    if col != metric and abs(corr_val) > 0.3:  # Only show significant
                        print(f"  {col:30s}: {corr_val:+.3f}")
        
        return corr_matrix
    
    def plot_parameter_sweep(self, test_type, param_column, 
                            metrics=['quality_score', 'mean_rms', 'mean_spectral_flatness']):
        """
        Visualize how metrics change with parameter values.
        
        Args:
            test_type: Test type to plot
            param_column: Parameter column (x-axis)
            metrics: List of metrics to plot (y-axes)
        """
        if self.merged_data is None:
            print("ERROR: No merged data. Run load_and_merge() first.")
            return
        
        df = self.merged_data
        subset = df[df['test_type'] == test_type].copy()
        
        if len(subset) == 0:
            print(f"No data for test_type '{test_type}'")
            return
        
        # Sort by parameter for cleaner plots
        subset = subset.sort_values(param_column)
        
        # Create figure with subplots
        n_metrics = len(metrics)
        fig, axes = plt.subplots(n_metrics, 1, figsize=(12, 4*n_metrics))
        
        if n_metrics == 1:
            axes = [axes]
        
        fig.suptitle(f'Parameter Sweep Analysis: {test_type}', 
                    fontsize=14, fontweight='bold')
        
        for i, metric in enumerate(metrics):
            if metric not in subset.columns:
                print(f"Warning: Metric '{metric}' not found, skipping")
                continue
            
            ax = axes[i]
            
            # Plot individual points
            ax.scatter(subset[param_column], subset[metric], 
                      alpha=0.6, s=100, color='steelblue', label='Measurements')
            
            # Plot trend line if enough points
            if len(subset) > 2:
                # Group by parameter and plot mean with error bars
                grouped = subset.groupby(param_column)[metric].agg(['mean', 'std', 'count'])
                grouped = grouped.reset_index()
                
                ax.errorbar(grouped[param_column], grouped['mean'], 
                           yerr=grouped['std'], fmt='o-', color='red', 
                           linewidth=2, markersize=8, capsize=5, 
                           label='Mean ± Std', zorder=10)
                
                # Mark optimal point
                best_idx = grouped['mean'].idxmax()
                best_param = grouped.loc[best_idx, param_column]
                best_value = grouped.loc[best_idx, 'mean']
                
                ax.axvline(best_param, color='green', linestyle='--', 
                          alpha=0.7, linewidth=2, 
                          label=f'Optimal: {best_param}')
                ax.plot(best_param, best_value, 'g*', 
                       markersize=20, zorder=15)
            
            ax.set_xlabel(param_column, fontsize=12)
            ax.set_ylabel(metric, fontsize=12)
            ax.set_title(f'{metric} vs {param_column}', fontsize=11)
            ax.grid(True, alpha=0.3)
            ax.legend()
        
        plt.tight_layout()
        
        # Save plot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plot_file = self.output_dir / f"{test_type}_{param_column}_sweep_{timestamp}.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"\nSaved parameter sweep plot: {plot_file}")
        plt.close()
    
    def plot_correlation_heatmap(self, test_type=None, save=True):
        """
        Plot correlation heatmap.
        
        Args:
            test_type: Optional test type filter
            save: Whether to save the plot
        """
        corr_matrix = self.correlation_analysis(test_type)
        
        if corr_matrix is None:
            return
        
        # Select subset of most interesting columns
        interesting_cols = [
            'midi_note', 'parameter', 'force_level', 'velocity',
            'peak_amplitude', 'mean_rms', 'mean_spectral_flatness',
            'snr_estimate', 'dynamic_range_db', 'quality_score',
            'fundamental_frequency', 'pitch_error_cents'
        ]
        
        available_cols = [col for col in interesting_cols if col in corr_matrix.columns]
        corr_subset = corr_matrix.loc[available_cols, available_cols]
        
        # Plot heatmap
        fig, ax = plt.subplots(figsize=(12, 10))
        
        im = ax.imshow(corr_subset, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Correlation', rotation=270, labelpad=20)
        
        # Set ticks
        ax.set_xticks(np.arange(len(available_cols)))
        ax.set_yticks(np.arange(len(available_cols)))
        ax.set_xticklabels(available_cols, rotation=45, ha='right')
        ax.set_yticklabels(available_cols)
        
        # Add correlation values as text
        for i in range(len(available_cols)):
            for j in range(len(available_cols)):
                text = ax.text(j, i, f'{corr_subset.iloc[i, j]:.2f}',
                             ha='center', va='center', color='black', fontsize=8)
        
        title = f'Correlation Heatmap'
        if test_type:
            title += f' - {test_type}'
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        if save:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            prefix = f"{test_type}_" if test_type else ""
            plot_file = self.output_dir / f"{prefix}correlation_heatmap_{timestamp}.png"
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            print(f"\nSaved correlation heatmap: {plot_file}")
        
        plt.close()
    
    def export_ml_dataset(self, output_file=None, test_type=None):
        """
        Export merged data as ML-ready dataset.
        
        Args:
            output_file: Output CSV file path (default: auto-generated)
            test_type: Optional filter for specific test type
            
        Returns:
            Path to exported file
        """
        if self.merged_data is None:
            print("ERROR: No merged data. Run load_and_merge() first.")
            return None
        
        df = self.merged_data
        
        if test_type:
            df = df[df['test_type'] == test_type]
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            prefix = f"{test_type}_" if test_type else ""
            output_file = self.output_dir / f"{prefix}ml_dataset_{timestamp}.csv"
        else:
            output_file = Path(output_file)
        
        df.to_csv(output_file, index=False)
        
        print(f"\n✓ Exported ML dataset: {output_file}")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        
        return output_file
    
    def generate_report(self, test_type=None):
        """
        Generate comprehensive analysis report.
        
        Args:
            test_type: Optional filter for specific test type
        """
        if self.merged_data is None:
            print("ERROR: No merged data. Run load_and_merge() first.")
            return
        
        print(f"\n{'='*60}")
        print(f"COMPREHENSIVE CROSS-ANALYSIS REPORT")
        print(f"{'='*60}\n")
        
        # 1. Basic statistics
        stats = self.analyze_by_test_type(test_type)
        
        # 2. Correlation analysis
        corr = self.correlation_analysis(test_type)
        
        # 3. Export report as JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = f"{test_type}_" if test_type else ""
        report_file = self.output_dir / f"{prefix}analysis_report_{timestamp}.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_type_filter': test_type,
            'total_recordings': len(self.merged_data),
            'statistics': stats,
            'correlation_matrix': corr.to_dict() if corr is not None else None
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✓ Report saved: {report_file}")


# Example usage and CLI
if __name__ == "__main__":
    import sys
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         GuitarBot Cross-Analysis Tool                         ║
║         Merge Metadata + Audio Analysis for ML/Optimization   ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    analyzer = CrossAnalyzer()
    
    # Default paths
    default_sessions = {
        'fretting_force': {
            'metadata': 'Recording/output/fretting_force_optimization/session_summary.csv',
            'analysis': 'Recording/analysis/audio_analysis_summary.csv'
        },
        'dynamics': {
            'metadata': 'Recording/output/dynamics_sweep/session_summary.csv',
            'analysis': 'Recording/analysis/audio_analysis_summary.csv'
        }
    }
    
    if len(sys.argv) >= 3:
        # User provided paths
        metadata_path = sys.argv[1]
        analysis_path = sys.argv[2]
        
        print(f"\nUsing provided paths:")
        print(f"  Metadata: {metadata_path}")
        print(f"  Analysis: {analysis_path}")
        
        merged = analyzer.load_and_merge(metadata_path, analysis_path)
        
        if merged is not None:
            # Run full analysis
            analyzer.generate_report()
            
            # Try to detect test type and parameter
            if 'test_type' in merged.columns:
                for test_type in merged['test_type'].unique():
                    print(f"\n--- Analyzing {test_type} ---")
                    
                    # Detect parameter column
                    param_cols = ['force_level', 'velocity', 'parameter']
                    param_col = None
                    for pc in param_cols:
                        if pc in merged.columns:
                            param_col = pc
                            break
                    
                    if param_col:
                        analyzer.find_optimal_parameters(test_type, param_col)
                        analyzer.plot_parameter_sweep(test_type, param_col)
                        analyzer.plot_correlation_heatmap(test_type)
            
            analyzer.export_ml_dataset()
    
    else:
        # Interactive mode - look for available sessions
        print("\nLooking for available recording sessions...")
        
        found_sessions = []
        for session_name, paths in default_sessions.items():
            metadata_path = Path(paths['metadata'])
            analysis_path = Path(paths['analysis'])
            
            if metadata_path.exists() and analysis_path.exists():
                found_sessions.append((session_name, metadata_path, analysis_path))
                print(f"  ✓ Found: {session_name}")
        
        if not found_sessions:
            print("\nNo sessions found with default paths.")
            print("\nUsage:")
            print("  python CrossAnalysis.py <metadata.csv> <analysis.csv>")
            print("\nExample:")
            print("  python CrossAnalysis.py Recording/output/fretting_force_optimization/session_summary.csv Recording/analysis/audio_analysis_summary.csv")
        else:
            print(f"\nAnalyzing all {len(found_sessions)} session(s)...\n")
            
            for session_name, metadata_path, analysis_path in found_sessions:
                print(f"\n{'='*60}")
                print(f"SESSION: {session_name}")
                print(f"{'='*60}")
                
                merged = analyzer.load_and_merge(metadata_path, analysis_path)
                
                if merged is not None:
                    # Analyze this session
                    test_types = merged['test_type'].unique() if 'test_type' in merged.columns else []
                    
                    for test_type in test_types:
                        print(f"\n--- Analyzing {test_type} ---")
                        
                        # Find parameter column
                        param_cols = ['force_level', 'velocity', 'parameter']
                        param_col = None
                        for pc in param_cols:
                            if pc in merged.columns and merged[merged['test_type'] == test_type][pc].notna().any():
                                param_col = pc
                                break
                        
                        if param_col:
                            # Find optimal parameters
                            optimal = analyzer.find_optimal_parameters(test_type, param_col)
                            
                            # Create visualizations
                            analyzer.plot_parameter_sweep(test_type, param_col)
                            analyzer.plot_correlation_heatmap(test_type)
                    
                    # Generate comprehensive report
                    analyzer.generate_report()
                    
                    # Export ML dataset
                    analyzer.export_ml_dataset()
    
    print("\n✓ Cross-analysis complete!")
    print(f"Results saved to: {analyzer.output_dir}")
