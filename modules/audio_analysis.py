"""Audio analysis module for BPM and key detection"""
import librosa
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from sqlalchemy import func

from database.db import db_manager
from database.models import File, AudioAnalysis, Migration
from config import config

logger = logging.getLogger(__name__)

# Musical key mappings
KEY_NAMES = {
    0: 'C', 1: 'C#', 2: 'D', 3: 'D#',
    4: 'E', 5: 'F', 6: 'F#', 7: 'G',
    8: 'G#', 9: 'A', 10: 'A#', 11: 'B'
}

class AudioAnalyzer:
    def __init__(self):
        self.enabled = config.get('audio_analysis.enabled', True)
        self.bpm_detection = config.get('audio_analysis.bpm_detection', True)
        self.key_detection = config.get('audio_analysis.key_detection', True)
        self.batch_size = config.get('audio_analysis.batch_size', 10)
        self.progress_callback = None
        self.should_stop = False
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def stop(self):
        """Signal to stop analysis"""
        self.should_stop = True
    
    def analyze_library(self, use_migrated_paths: bool = True) -> Dict[str, Any]:
        """
        Analyze all audio files in the library
        
        Args:
            use_migrated_paths: Whether to use migrated paths if available
        
        Returns:
            Dictionary with analysis results
        """
        if not self.enabled:
            logger.info("Audio analysis is disabled in configuration")
            return {'message': 'Audio analysis disabled'}
        
        logger.info("Starting audio analysis...")
        
        analyzed = 0
        failed = 0
        errors = []
        
        try:
            with db_manager.get_session() as session:
                # Get files without audio analysis
                query = session.query(File).outerjoin(AudioAnalysis).filter(
                    AudioAnalysis.file_id.is_(None)
                )
                
                if use_migrated_paths:
                    # Prefer migrated files
                    query = query.filter(File.status == 'migrated')
                
                files = query.all()
                total_files = len(files)
                
                logger.info(f"Analyzing {total_files} audio files")
                
                for i, file in enumerate(files):
                    if self.should_stop:
                        logger.info("Analysis stopped by user")
                        break
                    
                    # Determine file path
                    file_path = file.source_path
                    if use_migrated_paths:
                        migration = session.query(Migration).filter_by(
                            file_id=file.id,
                            status='completed'
                        ).first()
                        if migration:
                            file_path = migration.target_path
                    
                    try:
                        # Analyze audio file
                        analysis = self.analyze_file(file_path)
                        
                        if analysis:
                            # Save to database
                            audio_analysis = AudioAnalysis(
                                file_id=file.id,
                                bpm=analysis.get('bpm'),
                                key_signature=analysis.get('key'),
                                energy=analysis.get('energy'),
                                danceability=analysis.get('danceability'),
                                loudness_db=analysis.get('loudness'),
                                dynamic_range=analysis.get('dynamic_range'),
                                analyzed_at=datetime.utcnow()
                            )
                            session.add(audio_analysis)
                            analyzed += 1
                        else:
                            failed += 1
                    
                    except Exception as e:
                        logger.error(f"Error analyzing {file_path}: {e}")
                        errors.append(file_path)
                        failed += 1
                    
                    # Commit periodically
                    if i % self.batch_size == 0:
                        session.commit()
                    
                    # Update progress
                    if self.progress_callback:
                        self.progress_callback({
                            'operation': 'audio_analysis',
                            'progress': i + 1,
                            'total': total_files,
                            'message': f"Analyzing audio: {i + 1}/{total_files}"
                        })
                
                session.commit()
        
        except Exception as e:
            logger.error(f"Fatal error during audio analysis: {e}")
            raise
        
        logger.info(f"Audio analysis complete: {analyzed} analyzed, {failed} failed")
        
        return {
            'analyzed': analyzed,
            'failed': failed,
            'errors': len(errors),
            'error_files': errors[:10]
        }
    
    def analyze_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single audio file
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Dictionary with analysis results or None if analysis fails
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"File does not exist: {file_path}")
            return None
        
        try:
            # Load audio file (mono, 22050 Hz for faster processing)
            y, sr = librosa.load(str(path), mono=True, sr=22050)
            
            analysis = {}
            
            # BPM detection
            if self.bpm_detection:
                bpm = self._detect_bpm(y, sr)
                if bpm:
                    analysis['bpm'] = bpm
            
            # Key detection
            if self.key_detection:
                key = self._detect_key(y, sr)
                if key:
                    analysis['key'] = key
            
            # Energy and danceability
            energy, danceability = self._calculate_energy_danceability(y, sr)
            analysis['energy'] = energy
            analysis['danceability'] = danceability
            
            # Loudness and dynamic range
            loudness, dynamic_range = self._calculate_loudness(y)
            analysis['loudness'] = loudness
            analysis['dynamic_range'] = dynamic_range
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return None
    
    def _detect_bpm(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Detect BPM using librosa's tempo detection"""
        try:
            # Use onset detection for better tempo estimation
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            
            # Detect tempo
            tempo, beats = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=sr
            )
            
            # Round to 1 decimal place
            return round(float(tempo), 1)
        
        except Exception as e:
            logger.debug(f"Error detecting BPM: {e}")
            return None
    
    def _detect_key(self, y: np.ndarray, sr: int) -> Optional[str]:
        """Detect musical key using chromagram"""
        try:
            # Compute chromagram
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            
            # Calculate mean chroma vector
            chroma_mean = np.mean(chroma, axis=1)
            
            # Find dominant pitch class
            key_index = np.argmax(chroma_mean)
            
            # Determine if major or minor (simplified heuristic)
            # Check for presence of minor third
            minor_third = (key_index + 3) % 12
            major_third = (key_index + 4) % 12
            
            if chroma_mean[minor_third] > chroma_mean[major_third]:
                mode = 'm'  # Minor
            else:
                mode = ''  # Major
            
            key_name = KEY_NAMES[key_index] + mode
            
            return key_name
        
        except Exception as e:
            logger.debug(f"Error detecting key: {e}")
            return None
    
    def _calculate_energy_danceability(self, y: np.ndarray, sr: int) -> tuple[float, float]:
        """Calculate energy and danceability metrics"""
        try:
            # Calculate RMS energy
            rms = librosa.feature.rms(y=y)[0]
            energy = float(np.mean(rms))
            
            # Calculate spectral centroid (brightness)
            cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            brightness = float(np.mean(cent))
            
            # Simple danceability heuristic based on energy and tempo regularity
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
            
            # Calculate beat regularity
            if len(beats) > 1:
                beat_times = librosa.frames_to_time(beats, sr=sr)
                beat_intervals = np.diff(beat_times)
                beat_regularity = 1.0 - np.std(beat_intervals) / np.mean(beat_intervals)
            else:
                beat_regularity = 0.5
            
            # Combine factors for danceability (0-1 scale)
            danceability = (energy * 0.3 + beat_regularity * 0.5 + 
                          min(brightness / 5000, 1.0) * 0.2)
            danceability = float(min(max(danceability, 0), 1))
            
            return float(energy), danceability
        
        except Exception as e:
            logger.debug(f"Error calculating energy/danceability: {e}")
            return 0.0, 0.0
    
    def _calculate_loudness(self, y: np.ndarray) -> tuple[float, float]:
        """Calculate loudness and dynamic range"""
        try:
            # Calculate RMS in dB
            rms = librosa.feature.rms(y=y)[0]
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)
            
            # Mean loudness
            loudness = float(np.mean(rms_db))
            
            # Dynamic range (difference between loud and quiet parts)
            percentile_95 = np.percentile(rms_db, 95)
            percentile_5 = np.percentile(rms_db, 5)
            dynamic_range = float(percentile_95 - percentile_5)
            
            return loudness, dynamic_range
        
        except Exception as e:
            logger.debug(f"Error calculating loudness: {e}")
            return -30.0, 10.0
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get audio analysis statistics from database"""
        try:
            with db_manager.get_session() as session:
                total_analyzed = session.query(AudioAnalysis).count()
                
                if total_analyzed == 0:
                    return {'total_analyzed': 0}
                
                # Average BPM
                avg_bpm = session.query(func.avg(AudioAnalysis.bpm)).scalar() or 0
                
                # Key distribution
                key_distribution = {}
                for key, count in session.query(
                    AudioAnalysis.key_signature,
                    func.count()
                ).group_by(AudioAnalysis.key_signature).all():
                    if key:
                        key_distribution[key] = count
                
                # Average metrics
                avg_energy = session.query(func.avg(AudioAnalysis.energy)).scalar() or 0
                
                avg_danceability = session.query(func.avg(AudioAnalysis.danceability)).scalar() or 0
                
                return {
                    'total_analyzed': total_analyzed,
                    'average_bpm': round(avg_bpm, 1),
                    'key_distribution': key_distribution,
                    'average_energy': round(avg_energy, 3),
                    'average_danceability': round(avg_danceability, 3)
                }
        
        except Exception as e:
            logger.error(f"Error getting analysis statistics: {e}")
            return {}