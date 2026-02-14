"""
Audio Converter Utility
========================

Utility class for audio conversion and FFmpeg availability checking.
"""

import os
import subprocess
import shutil
import tempfile
import requests
from io import BytesIO
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
    
    def needs_conversion(self, mime_type: str) -> bool:
        """
        Check if audio format needs conversion to WAV for STT.
        
        Args:
            mime_type: MIME type of the audio file
            
        Returns:
            bool: True if conversion needed, False otherwise
        """
        # Formats that need conversion
        conversion_needed = [
            'audio/webm',
            'audio/ogg',
            'audio/opus',
            'audio/x-m4a',
            'audio/aac'
        ]
        
        return mime_type in conversion_needed
    
    def convert_to_wav(self, audio_url: str) -> Optional[BytesIO]:
        """
        Convert audio from URL to WAV format (16kHz, mono, LINEAR16).
        
        Args:
            audio_url: URL of the audio file to convert
            
        Returns:
            BytesIO: WAV audio data or None if failed
        """
        if not self.is_ffmpeg_available():
            print("❌ FFmpeg not available for audio conversion")
            return None
        
        temp_input = None
        temp_output = None
        
        try:
            # Download audio from URL
            print(f"   📥 Downloading audio from URL...")
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_input:
                temp_input.write(response.content)
                temp_input_path = temp_input.name
            
            # Create temp output file
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_output_path = temp_output.name
            temp_output.close()
            
            # Convert using FFmpeg
            print(f"   🔄 Converting to WAV (16kHz, mono)...")
            cmd = [
                self.ffmpeg_path,
                '-i', temp_input_path,
                '-ar', '16000',        # Sample rate: 16kHz
                '-ac', '1',            # Channels: mono
                '-acodec', 'pcm_s16le',  # Codec: LINEAR16
                '-y',                  # Overwrite
                temp_output_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"❌ FFmpeg conversion failed: {result.stderr}")
                return None
            
            # Read converted file
            with open(temp_output_path, 'rb') as f:
                wav_data = BytesIO(f.read())
            
            print(f"   ✅ Conversion successful")
            return wav_data
            
        except Exception as e:
            print(f"❌ Conversion error: {e}")
            return None
            
        finally:
            # Cleanup temp files
            try:
                if temp_input_path and os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
                if temp_output_path and os.path.exists(temp_output_path):
                    os.unlink(temp_output_path)
            except:
                pass
    
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