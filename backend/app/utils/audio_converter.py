"""
Audio Converter Utility
========================

Utility class for audio conversion and FFmpeg availability checking.
"""

import os
import subprocess
import shutil
from typing import Optional


class AudioConverter:
    """Audio converter utility with FFmpeg support."""
    
    def __init__(self):
        """Initialize the audio converter."""
        self.ffmpeg_path = self._find_ffmpeg()
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable in system PATH."""
        return shutil.which('ffmpeg')
    
    def is_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available on the system."""
        if self.ffmpeg_path:
            try:
                # Test FFmpeg by running version command
                result = subprocess.run(
                    [self.ffmpeg_path, '-version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                return False
        return False
    
    def convert_audio(self, input_path: str, output_path: str, format: str = 'mp3') -> bool:
        """
        Convert audio file to specified format.
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file
            format: Output format (mp3, wav, etc.)
            
        Returns:
            bool: True if conversion successful, False otherwise
        """
        if not self.is_ffmpeg_available():
            print("❌ FFmpeg not available for audio conversion")
            return False
        
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-y',  # Overwrite output file
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Audio conversion failed: {e}")
            return False