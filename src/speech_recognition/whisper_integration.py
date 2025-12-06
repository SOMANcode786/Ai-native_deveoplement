"""
Whisper Integration Module for Vision-Language-Action (VLA) System

This module provides integration with OpenAI Whisper for speech recognition
in the VLA system. It includes both API-based and local model options.
"""

import asyncio
import io
import os
import logging
from typing import Optional, Dict, Any, Union, BinaryIO
from pathlib import Path

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

try:
    import torch
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None
    torch = None


class WhisperIntegration:
    """
    Integration class for OpenAI Whisper speech recognition
    Supports both OpenAI API and local model options
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "base", use_local: bool = True):
        """
        Initialize Whisper integration

        Args:
            api_key: OpenAI API key (required if using API)
            model_name: Whisper model name ('tiny', 'base', 'small', 'medium', 'large', 'large-v2')
            use_local: Whether to use local model (True) or OpenAI API (False)
        """
        self.api_key = api_key
        self.model_name = model_name
        self.use_local = use_local
        self.logger = logging.getLogger(__name__)

        # Initialize Whisper model if using local
        if self.use_local and WHISPER_AVAILABLE:
            try:
                self.model = whisper.load_model(self.model_name)
                self.logger.info(f"Loaded Whisper model: {self.model_name}")
            except Exception as e:
                self.logger.error(f"Failed to load Whisper model: {e}")
                self.model = None
        else:
            self.model = None

        # Initialize OpenAI client if using API
        if not self.use_local and OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = AsyncOpenAI(api_key=self.api_key)
                self.logger.info("Initialized OpenAI Whisper client")
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            self.client = None

    async def transcribe_audio(self, audio_data: Union[bytes, str, BinaryIO],
                              language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe audio data using Whisper

        Args:
            audio_data: Audio data as bytes, file path string, or file-like object
            language: Language code (e.g., 'en', 'es', 'fr') or None for auto-detection

        Returns:
            Dictionary containing transcription result with keys:
            - 'text': Transcribed text
            - 'language': Detected language
            - 'confidence': Confidence score (0.0-1.0)
            - 'duration': Audio duration
            - 'segments': List of transcription segments (if available)
        """
        if self.use_local and self.model is not None:
            return await self._transcribe_with_local_model(audio_data, language)
        elif not self.use_local and self.client is not None:
            return await self._transcribe_with_api(audio_data, language)
        else:
            raise RuntimeError("Neither local model nor API client is available")

    async def _transcribe_with_local_model(self, audio_data: Union[bytes, str, BinaryIO],
                                         language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio using local Whisper model"""
        try:
            # Handle different input types
            if isinstance(audio_data, str):
                # File path
                result = self.model.transcribe(audio_data, language=language)
            elif isinstance(audio_data, bytes):
                # Raw audio bytes - need to save to temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = temp_file.name

                try:
                    result = self.model.transcribe(temp_path, language=language)
                finally:
                    # Clean up temporary file
                    os.unlink(temp_path)
            elif hasattr(audio_data, 'read'):
                # File-like object - save to temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(audio_data.read())
                    temp_path = temp_file.name

                try:
                    result = self.model.transcribe(temp_path, language=language)
                finally:
                    # Clean up temporary file
                    os.unlink(temp_path)
            else:
                raise ValueError(f"Unsupported audio data type: {type(audio_data)}")

            # Format the result
            transcription_result = {
                'text': result['text'].strip(),
                'language': result.get('language', language or 'unknown'),
                'confidence': self._estimate_confidence(result['text']),
                'duration': result.get('duration', 0),
                'segments': [
                    {
                        'start': segment.get('start', 0),
                        'end': segment.get('end', 0),
                        'text': segment.get('text', '').strip(),
                        'confidence': segment.get('avg_logprob', 0) if 'avg_logprob' in segment else 0.5
                    }
                    for segment in result.get('segments', [])
                ] if 'segments' in result else []
            }

            self.logger.info(f"Local Whisper transcription completed: {len(transcription_result['text'])} chars")
            return transcription_result

        except Exception as e:
            self.logger.error(f"Error in local Whisper transcription: {e}")
            raise

    async def _transcribe_with_api(self, audio_data: Union[bytes, str, BinaryIO],
                                 language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio using OpenAI Whisper API"""
        if not OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI library not available")
        if self.client is None:
            raise RuntimeError("OpenAI client not initialized")

        try:
            # Handle different input types
            if isinstance(audio_data, str):
                # File path
                with open(audio_data, 'rb') as audio_file:
                    response = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )
            elif isinstance(audio_data, bytes):
                # Raw audio bytes - need to wrap in BytesIO
                import io
                audio_io = io.BytesIO(audio_data)
                audio_io.name = 'audio.wav'  # Required by OpenAI API
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_io,
                    language=language
                )
            elif hasattr(audio_data, 'read'):
                # File-like object
                audio_io = io.BytesIO(audio_data.read())
                audio_io.name = getattr(audio_data, 'name', 'audio.wav')
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_io,
                    language=language
                )
            else:
                raise ValueError(f"Unsupported audio data type: {type(audio_data)}")

            # Format the result
            transcription_result = {
                'text': response.text.strip(),
                'language': language or 'unknown',  # API doesn't return language in response
                'confidence': 0.9,  # API doesn't provide confidence, assume high
                'duration': 0,  # API doesn't provide duration
                'segments': []  # API doesn't provide segments in basic transcription
            }

            self.logger.info(f"API Whisper transcription completed: {len(transcription_result['text'])} chars")
            return transcription_result

        except Exception as e:
            self.logger.error(f"Error in API Whisper transcription: {e}")
            raise

    def _estimate_confidence(self, text: str) -> float:
        """
        Estimate confidence based on text characteristics
        This is a simple heuristic - in a real system, use actual model probabilities
        """
        if not text or len(text.strip()) == 0:
            return 0.0

        # Simple confidence estimation based on text length and characteristics
        text_length = len(text.strip())
        if text_length < 5:
            # Very short text might be unreliable
            return 0.3
        elif text_length > 100:
            # Longer text is more likely to be meaningful
            return 0.9
        else:
            # Medium length text
            return 0.7

    async def transcribe_with_timing(self, audio_data: Union[bytes, str, BinaryIO],
                                   language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe audio and include detailed timing information
        This method provides segment-level timing for better synchronization
        """
        result = await self.transcribe_audio(audio_data, language)

        # If we have segments from local model, return as-is
        if result['segments']:
            return result

        # For API results or models without segments, create a single segment
        return {
            **result,
            'segments': [{
                'start': 0,
                'end': result.get('duration', 0),
                'text': result['text'],
                'confidence': result['confidence']
            }]
        }

    async def batch_transcribe(self, audio_files: list, language: Optional[str] = None) -> list:
        """
        Transcribe multiple audio files in parallel
        """
        tasks = [self.transcribe_audio(audio_file, language) for audio_file in audio_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions in the results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Error transcribing file {i}: {result}")
                processed_results.append({
                    'error': str(result),
                    'text': '',
                    'confidence': 0.0
                })
            else:
                processed_results.append(result)

        return processed_results


# Utility functions for audio processing
def validate_audio_format(audio_data: Union[bytes, str, BinaryIO]) -> bool:
    """
    Validate that audio data is in a supported format
    """
    if isinstance(audio_data, str):
        # Check file extension
        path = Path(audio_data)
        return path.suffix.lower() in ['.wav', '.mp3', '.m4a', '.mp4', '.mpeg', '.mpga', '.webm']
    elif isinstance(audio_data, bytes):
        # Check for common audio headers
        if len(audio_data) < 12:
            return False

        # Check for WAV header
        if audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE':
            return True

        # Check for MP3 header (simplified)
        if audio_data[0:3] == b'\xff\xfb' or audio_data[0:3] == b'\xff\xf3' or audio_data[0:3] == b'\xff\xf2':
            return True

        return False
    elif hasattr(audio_data, 'read'):
        # File-like object - assume valid for now
        return True
    else:
        return False


def normalize_audio(audio_data: bytes, target_sample_rate: int = 16000) -> bytes:
    """
    Normalize audio data to target sample rate
    This is a simplified version - in practice, use librosa or pydub
    """
    # In a real implementation, this would use audio processing libraries
    # to resample audio to the target sample rate
    return audio_data


# Example usage and testing
async def main():
    """Example usage of Whisper integration"""
    import sys

    # Check if required libraries are available
    if not WHISPER_AVAILABLE and not OPENAI_AVAILABLE:
        print("Error: Neither whisper nor openai libraries are available")
        print("Install with: pip install openai or pip install openai-whisper")
        sys.exit(1)

    # Initialize Whisper integration
    # Use local model if available, otherwise try API
    if WHISPER_AVAILABLE:
        print("Using local Whisper model...")
        whisper_int = WhisperIntegration(model_name="base", use_local=True)
    elif OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set")
            sys.exit(1)
        print("Using OpenAI Whisper API...")
        whisper_int = WhisperIntegration(api_key=api_key, use_local=False)
    else:
        print("No Whisper implementation available")
        sys.exit(1)

    # Example: Transcribe a text command (in practice, this would be audio data)
    # For demonstration, we'll simulate with a temporary file
    sample_text = "Please clean the table and move the red block to the blue area."

    # In a real scenario, you would have actual audio data
    # For now, this demonstrates the API usage
    print(f"Whisper integration initialized successfully")
    print(f"Model: {'Local Whisper' if whisper_int.use_local else 'OpenAI API'}")


if __name__ == "__main__":
    asyncio.run(main())