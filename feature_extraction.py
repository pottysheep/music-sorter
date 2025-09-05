"""
Extended feature extraction for audio classification EDA
"""
import numpy as np
import librosa
import torch
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """Extract comprehensive features for audio classification"""
    
    def __init__(self, sr: int = 22050):
        """
        Initialize feature extractor
        
        Args:
            sr: Sample rate for audio loading
        """
        self.sr = sr
        
        # Keywords that might indicate file type
        self.sample_keywords = [
            'loop', 'kick', 'snare', 'hat', 'hihat', 'perc', 'percussion',
            'drum', 'bass', 'synth', 'pad', 'lead', 'fx', 'sfx', 'effect',
            'one_shot', 'oneshot', 'hit', 'stab', 'riser', 'sweep', 'impact',
            'crash', 'cymbal', 'clap', 'rim', 'tom', 'fill'
        ]
        
        self.stem_keywords = [
            'stem', 'vocal', 'vox', 'instrumental', 'inst', 'acapella',
            'drums', 'bass', 'melody', 'harmony', 'dry', 'wet', 'isolated',
            'backing', 'lead_vocal', 'bgv', 'strings', 'keys', 'guitar'
        ]
        
        self.song_keywords = [
            'master', 'final', 'mix', 'album', 'track', 'song', 'full',
            'complete', 'radio', 'edit', 'version', 'remix', 'original'
        ]
    
    def extract_all_features(self, file_path: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract all features from an audio file
        
        Args:
            file_path: Path to audio file
            metadata: Optional metadata dictionary
        
        Returns:
            Dictionary of features
        """
        features = {}
        path = Path(file_path)
        
        try:
            # Basic file features
            features.update(self._extract_file_features(path))
            
            # Path and naming features
            features.update(self._extract_path_features(path))
            
            # Load audio
            y, sr = librosa.load(str(path), sr=self.sr, mono=True)
            
            # Temporal features
            features.update(self._extract_temporal_features(y, sr))
            
            # Spectral features
            features.update(self._extract_spectral_features(y, sr))
            
            # Rhythmic features
            features.update(self._extract_rhythmic_features(y, sr))
            
            # Harmonic features
            features.update(self._extract_harmonic_features(y, sr))
            
            # Statistical features
            features.update(self._extract_statistical_features(y, sr))
            
            # Metadata features if available
            if metadata:
                features.update(self._extract_metadata_features(metadata))
            
            # Add file path for reference
            features['file_path'] = str(path)
            
        except Exception as e:
            logger.error(f"Error extracting features from {file_path}: {e}")
            features['error'] = str(e)
            features['file_path'] = str(path)
        
        return features
    
    def _extract_file_features(self, path: Path) -> Dict[str, Any]:
        """Extract basic file features"""
        return {
            'file_size_mb': path.stat().st_size / (1024 * 1024),
            'extension': path.suffix.lower(),
            'filename_length': len(path.stem)
        }
    
    def _extract_path_features(self, path: Path) -> Dict[str, Any]:
        """Extract path and naming pattern features"""
        features = {}
        
        # Path depth (how many folders deep)
        features['path_depth'] = len(path.parts) - 1
        
        # Convert to lowercase for keyword matching
        full_path_lower = str(path).lower()
        filename_lower = path.stem.lower()
        
        # Keyword presence
        features['has_sample_keyword'] = any(kw in full_path_lower for kw in self.sample_keywords)
        features['has_stem_keyword'] = any(kw in full_path_lower for kw in self.stem_keywords)
        features['has_song_keyword'] = any(kw in full_path_lower for kw in self.song_keywords)
        
        # Count keyword matches
        features['sample_keyword_count'] = sum(1 for kw in self.sample_keywords if kw in full_path_lower)
        features['stem_keyword_count'] = sum(1 for kw in self.stem_keywords if kw in full_path_lower)
        features['song_keyword_count'] = sum(1 for kw in self.song_keywords if kw in full_path_lower)
        
        # Naming patterns
        features['has_number_prefix'] = bool(re.match(r'^\d+', filename_lower))
        features['has_artist_title_pattern'] = bool(re.search(r'.+\s*-\s*.+', filename_lower))
        features['has_version_indicator'] = bool(re.search(r'v\d+|version|edit|remix|mix', filename_lower))
        
        # Folder name features
        parent_folder = path.parent.name.lower() if path.parent else ""
        features['parent_has_sample_keyword'] = any(kw in parent_folder for kw in self.sample_keywords)
        features['parent_has_stem_keyword'] = any(kw in parent_folder for kw in self.stem_keywords)
        features['parent_has_song_keyword'] = any(kw in parent_folder for kw in self.song_keywords)
        
        return features
    
    def _extract_temporal_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract temporal features"""
        features = {}
        
        # Duration
        features['duration_seconds'] = len(y) / sr
        
        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)
        features['zcr_mean'] = float(np.mean(zcr))
        features['zcr_std'] = float(np.std(zcr))
        
        # RMS energy
        rms = librosa.feature.rms(y=y)
        features['rms_mean'] = float(np.mean(rms))
        features['rms_std'] = float(np.std(rms))
        
        # Silence ratio (frames below threshold)
        silence_threshold = np.percentile(np.abs(y), 10)
        features['silence_ratio'] = float(np.sum(np.abs(y) < silence_threshold) / len(y))
        
        # Dynamic range
        features['dynamic_range'] = float(np.max(np.abs(y)) - np.min(np.abs(y)))
        
        return features
    
    def _extract_spectral_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract spectral features"""
        features = {}
        
        # Spectral centroid (brightness)
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
        features['spectral_centroid_mean'] = float(np.mean(spectral_centroids))
        features['spectral_centroid_std'] = float(np.std(spectral_centroids))
        
        # Spectral bandwidth
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        features['spectral_bandwidth_mean'] = float(np.mean(spectral_bandwidth))
        features['spectral_bandwidth_std'] = float(np.std(spectral_bandwidth))
        
        # Spectral rolloff
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        features['spectral_rolloff_mean'] = float(np.mean(spectral_rolloff))
        features['spectral_rolloff_std'] = float(np.std(spectral_rolloff))
        
        # Spectral contrast
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        features['spectral_contrast_mean'] = float(np.mean(spectral_contrast))
        features['spectral_contrast_std'] = float(np.std(spectral_contrast))
        
        # MFCCs (13 coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        for i in range(13):
            features[f'mfcc_{i}_mean'] = float(np.mean(mfccs[i]))
            features[f'mfcc_{i}_std'] = float(np.std(mfccs[i]))
        
        return features
    
    def _extract_rhythmic_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract rhythmic features"""
        features = {}
        
        # Onset detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time')
        
        features['onset_count'] = len(onsets)
        features['onset_density'] = len(onsets) / (len(y) / sr) if len(y) > 0 else 0
        
        # Tempo and beat tracking
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        features['tempo'] = float(tempo)
        features['beat_count'] = len(beats)
        
        # Beat regularity (how consistent are the beat intervals)
        if len(beats) > 1:
            beat_times = librosa.frames_to_time(beats, sr=sr)
            beat_intervals = np.diff(beat_times)
            features['beat_regularity'] = float(1.0 - np.std(beat_intervals) / (np.mean(beat_intervals) + 1e-6))
            features['beat_interval_mean'] = float(np.mean(beat_intervals))
            features['beat_interval_std'] = float(np.std(beat_intervals))
        else:
            features['beat_regularity'] = 0.0
            features['beat_interval_mean'] = 0.0
            features['beat_interval_std'] = 0.0
        
        # Tempogram features (tempo stability)
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        features['tempogram_ratio'] = float(np.mean(tempogram))
        
        return features
    
    def _extract_harmonic_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract harmonic features"""
        features = {}
        
        # Chroma features (12 pitch classes)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        
        # Mean and std for each pitch class
        for i in range(12):
            features[f'chroma_{i}_mean'] = float(np.mean(chroma[i]))
            features[f'chroma_{i}_std'] = float(np.std(chroma[i]))
        
        # Overall chroma statistics
        features['chroma_mean'] = float(np.mean(chroma))
        features['chroma_std'] = float(np.std(chroma))
        
        # Harmonic-percussive separation
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        
        # Ratio of harmonic to percussive content
        harmonic_energy = np.sum(y_harmonic**2)
        percussive_energy = np.sum(y_percussive**2)
        total_energy = harmonic_energy + percussive_energy + 1e-10
        
        features['harmonic_ratio'] = float(harmonic_energy / total_energy)
        features['percussive_ratio'] = float(percussive_energy / total_energy)
        
        # Tonnetz (tonal centroid features)
        tonnetz = librosa.feature.tonnetz(y=y, sr=sr)
        features['tonnetz_mean'] = float(np.mean(tonnetz))
        features['tonnetz_std'] = float(np.std(tonnetz))
        
        return features
    
    def _extract_statistical_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract statistical features from the audio signal"""
        features = {}
        
        # Basic statistics
        features['signal_mean'] = float(np.mean(y))
        features['signal_std'] = float(np.std(y))
        features['signal_skewness'] = float(self._skewness(y))
        features['signal_kurtosis'] = float(self._kurtosis(y))
        
        # Percentiles
        features['signal_25_percentile'] = float(np.percentile(np.abs(y), 25))
        features['signal_50_percentile'] = float(np.percentile(np.abs(y), 50))
        features['signal_75_percentile'] = float(np.percentile(np.abs(y), 75))
        features['signal_95_percentile'] = float(np.percentile(np.abs(y), 95))
        
        # Crest factor (peak to RMS ratio)
        rms = np.sqrt(np.mean(y**2))
        peak = np.max(np.abs(y))
        features['crest_factor'] = float(peak / (rms + 1e-10))
        
        # Flatness (geometric mean / arithmetic mean of spectrum)
        spec = np.abs(np.fft.rfft(y))
        geometric_mean = np.exp(np.mean(np.log(spec + 1e-10)))
        arithmetic_mean = np.mean(spec)
        features['spectral_flatness'] = float(geometric_mean / (arithmetic_mean + 1e-10))
        
        return features
    
    def _extract_metadata_features(self, metadata: Dict) -> Dict[str, Any]:
        """Extract features from metadata"""
        features = {}
        
        # Metadata completeness
        metadata_fields = ['artist', 'title', 'album', 'year', 'genre']
        metadata_present = sum(1 for field in metadata_fields if metadata.get(field))
        features['metadata_completeness'] = metadata_present / len(metadata_fields)
        
        # Specific metadata flags
        features['has_artist'] = bool(metadata.get('artist'))
        features['has_title'] = bool(metadata.get('title'))
        features['has_album'] = bool(metadata.get('album'))
        features['has_year'] = bool(metadata.get('year'))
        features['has_genre'] = bool(metadata.get('genre'))
        
        # Technical metadata
        features['bitrate'] = metadata.get('bitrate', 0)
        features['sample_rate'] = metadata.get('sample_rate', 0)
        
        # Duration from metadata (might differ from audio analysis)
        features['metadata_duration'] = metadata.get('duration_seconds', 0)
        
        return features
    
    @staticmethod
    def _skewness(x):
        """Calculate skewness of a signal"""
        mean = np.mean(x)
        std = np.std(x)
        if std == 0:
            return 0
        return np.mean(((x - mean) / std) ** 3)
    
    @staticmethod
    def _kurtosis(x):
        """Calculate kurtosis of a signal"""
        mean = np.mean(x)
        std = np.std(x)
        if std == 0:
            return 0
        return np.mean(((x - mean) / std) ** 4) - 3

def extract_features_batch(file_paths: List[str], 
                          metadata_dict: Optional[Dict[str, Dict]] = None,
                          sr: int = 22050) -> List[Dict[str, Any]]:
    """
    Extract features from multiple files
    
    Args:
        file_paths: List of file paths
        metadata_dict: Optional dictionary mapping file paths to metadata
        sr: Sample rate
    
    Returns:
        List of feature dictionaries
    """
    extractor = FeatureExtractor(sr=sr)
    features_list = []
    
    for i, file_path in enumerate(file_paths):
        if i % 10 == 0:
            logger.info(f"Processing file {i+1}/{len(file_paths)}")
        
        metadata = metadata_dict.get(file_path) if metadata_dict else None
        features = extractor.extract_all_features(file_path, metadata)
        features_list.append(features)
    
    return features_list