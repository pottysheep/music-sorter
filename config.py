"""Configuration management for Music Sorter"""
import yaml
from pathlib import Path
from typing import Dict, Any

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Return default config if file doesn't exist
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "source": {
                "batch_size": 100,
                "io_threads": 1
            },
            "target": {
                "io_threads": 4,
                "base_path": "F:/music production"
            },
            "deduplication": {
                "min_song_size_mb": 2,
                "max_sample_size_mb": 0.5,
                "hash_chunk_size_mb": 1
            },
            "classification": {
                "categories": ["song", "sample", "stem", "unknown"],
                "thresholds": {
                    "sample_max_size_mb": 0.5,
                    "sample_max_duration_seconds": 30,
                    "stem_min_size_mb": 0.5,
                    "stem_max_size_mb": 10,
                    "stem_keywords": ["stem", "drums", "bass", "vocals", "instrumental", "acapella", "dry", "wet"],
                    "song_min_size_mb": 2,
                    "song_min_duration_seconds": 90
                },
                "ml_model": {
                    "enabled": False,
                    "model_path": "models/classifier.pkl",
                    "feature_extractors": ["duration", "file_size", "path_keywords", "filename_patterns"]
                }
            },
            "audio_analysis": {
                "enabled": True,
                "bpm_detection": True,
                "key_detection": True,
                "batch_size": 10
            },
            "api_keys": {
                "acoustid": "",
                "musicbrainz_user_agent": "MusicSorter/1.0"
            },
            "database": {
                "path": "music_library.db"
            },
            "logging": {
                "level": "INFO",
                "file": "music_sorter.log"
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000
            },
            "checkpoint": {
                "interval": 100,
                "enabled": True
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def save(self):
        """Save current configuration to file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)

# Global config instance
config = Config()