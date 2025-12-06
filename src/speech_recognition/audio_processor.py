"""
Audio Preprocessing Pipeline for Vision-Language-Action (VLA) System

This module provides comprehensive audio preprocessing capabilities
for the VLA system's speech recognition pipeline.
"""

import asyncio
import logging
import numpy as np
from typing import Optional, Union, Tuple, Dict, Any
from dataclasses import dataclass
from pathlib import Path

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    librosa = None

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False
    sf = None


@dataclass
class AudioProcessorConfig:
    """Configuration for audio preprocessing"""
    target_sample_rate: int = 16000
    target_channels: int = 1
    normalize_audio: bool = True
    remove_silence: bool = True
    noise_reduction: bool = True
    volume_threshold: float = 0.01
    silence_duration_threshold: float = 0.1  # seconds
    noise_reduction_strength: float = 0.5


class AudioProcessor:
    """
    Audio preprocessing pipeline for the VLA system
    Handles normalization, noise reduction, and format conversion
    """

    def __init__(self, config: Optional[AudioProcessorConfig] = None):
        self.config = config or AudioProcessorConfig()
        self.logger = logging.getLogger(__name__)

        # Validate required libraries are available
        if not LIBROSA_AVAILABLE:
            self.logger.warning("librosa not available - some preprocessing features will be limited")

    async def preprocess_audio(self, audio_data: Union[str, bytes, np.ndarray],
                              sample_rate: Optional[int] = None) -> Dict[str, Any]:
        """
        Preprocess audio data for speech recognition

        Args:
            audio_data: Audio data as file path, bytes, or numpy array
            sample_rate: Sample rate of input audio (required if audio_data is bytes/array)

        Returns:
            Dictionary containing:
            - 'processed_audio': Processed audio as numpy array
            - 'sample_rate': Output sample rate
            - 'duration': Audio duration in seconds
            - 'rms': Root mean square energy
            - 'preprocessing_steps': List of applied preprocessing steps
        """
        try:
            # Load audio data
            if isinstance(audio_data, str):
                # File path
                audio_array, loaded_sr = await self._load_audio_file(audio_data)
                sample_rate = loaded_sr
            elif isinstance(audio_data, bytes):
                # Raw audio bytes
                if sample_rate is None:
                    raise ValueError("Sample rate must be provided when audio_data is bytes")
                audio_array = await self._load_audio_bytes(audio_data, sample_rate)
            elif isinstance(audio_data, np.ndarray):
                # Numpy array
                if sample_rate is None:
                    raise ValueError("Sample rate must be provided when audio_data is numpy array")
                audio_array = audio_data
            else:
                raise ValueError(f"Unsupported audio data type: {type(audio_data)}")

            # Store original for comparison
            original_audio = audio_array.copy()
            preprocessing_steps = []

            # Convert to mono if multi-channel
            if audio_array.ndim > 1:
                audio_array = self._to_mono(audio_array)
                preprocessing_steps.append("converted_to_mono")

            # Resample to target rate
            if sample_rate != self.config.target_sample_rate:
                audio_array = self._resample_audio(audio_array, sample_rate, self.config.target_sample_rate)
                sample_rate = self.config.target_sample_rate
                preprocessing_steps.append(f"resampled_to_{self.config.target_sample_rate}hz")

            # Normalize audio
            if self.config.normalize_audio:
                audio_array = self._normalize_audio(audio_array)
                preprocessing_steps.append("normalized")

            # Remove silence
            if self.config.remove_silence:
                audio_array = self._remove_silence(audio_array, sample_rate)
                preprocessing_steps.append("silence_removed")

            # Apply noise reduction
            if self.config.noise_reduction and LIBROSA_AVAILABLE:
                audio_array = self._reduce_noise(audio_array, sample_rate)
                preprocessing_steps.append("noise_reduced")

            # Calculate metrics
            duration = len(audio_array) / sample_rate
            rms = self._calculate_rms(audio_array)

            result = {
                'processed_audio': audio_array,
                'sample_rate': sample_rate,
                'duration': duration,
                'rms': rms,
                'preprocessing_steps': preprocessing_steps,
                'original_duration': len(original_audio) / sample_rate if original_audio.size > 0 else 0
            }

            self.logger.info(
                f"Audio preprocessing completed: {len(preprocessing_steps)} steps applied, "
                f"duration: {duration:.2f}s, RMS: {rms:.4f}",
                extra={'preprocessing_steps': preprocessing_steps}
            )

            return result

        except Exception as e:
            self.logger.error(f"Error in audio preprocessing: {e}")
            raise

    async def _load_audio_file(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Load audio from file"""
        if not LIBROSA_AVAILABLE:
            raise RuntimeError("librosa required for file loading")

        try:
            audio, sample_rate = librosa.load(file_path, sr=None, mono=False)
            self.logger.debug(f"Loaded audio file: {file_path}, shape: {audio.shape}, sr: {sample_rate}")
            return audio, sample_rate
        except Exception as e:
            self.logger.error(f"Error loading audio file {file_path}: {e}")
            raise

    async def _load_audio_bytes(self, audio_bytes: bytes, sample_rate: int) -> np.ndarray:
        """Load audio from bytes"""
        if SOUNDFILE_AVAILABLE:
            # Try to load with soundfile first
            import io
            audio_io = io.BytesIO(audio_bytes)
            try:
                audio, _ = sf.read(audio_io)
                return audio
            except:
                pass  # Fall back to manual processing

        # Manual processing for raw audio bytes
        # Assume 16-bit PCM for now
        try:
            import struct
            # Calculate number of samples (assuming 16-bit)
            num_samples = len(audio_bytes) // 2
            # Unpack bytes to signed 16-bit integers
            samples = struct.unpack(f'{num_samples}h', audio_bytes)
            # Convert to numpy array and normalize to [-1, 1]
            audio_array = np.array(samples, dtype=np.float32) / 32768.0
            return audio_array
        except Exception as e:
            self.logger.error(f"Error processing raw audio bytes: {e}")
            raise

    def _to_mono(self, audio_array: np.ndarray) -> np.ndarray:
        """Convert multi-channel audio to mono"""
        if audio_array.ndim == 1:
            return audio_array

        # Average all channels
        if audio_array.ndim == 2:
            return np.mean(audio_array, axis=0)

        # For higher dimensions, take the first two channels average
        return np.mean(audio_array, axis=tuple(range(1, audio_array.ndim)))

    def _resample_audio(self, audio_array: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate"""
        if not LIBROSA_AVAILABLE:
            # Simple resampling using numpy (not as good as librosa but functional)
            duration = len(audio_array) / orig_sr
            target_length = int(duration * target_sr)
            indices = np.linspace(0, len(audio_array) - 1, target_length).astype(int)
            return audio_array[indices]

        # Use librosa for better resampling
        return librosa.resample(audio_array, orig_sr=orig_sr, target_sr=target_sr)

    def _normalize_audio(self, audio_array: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range"""
        max_amplitude = np.max(np.abs(audio_array))
        if max_amplitude > 0:
            return audio_array / max_amplitude
        return audio_array

    def _remove_silence(self, audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
        """Remove silence from beginning and end of audio"""
        if not LIBROSA_AVAILABLE:
            # Simple silence removal based on amplitude threshold
            threshold = self.config.volume_threshold

            # Find non-silent regions
            non_silent = np.where(np.abs(audio_array) > threshold)[0]
            if len(non_silent) == 0:
                # All audio is silent, return empty
                return np.array([])

            start_idx = non_silent[0]
            end_idx = non_silent[-1] + 1

            return audio_array[start_idx:end_idx]

        # Use librosa for more sophisticated silence removal
        intervals = librosa.effects.split(
            audio_array,
            top_db=-20 * np.log10(self.config.volume_threshold),  # Convert to dB
            frame_length=2048,
            hop_length=512
        )

        if len(intervals) == 0:
            return np.array([])

        # Concatenate non-silent intervals
        non_silent_audio = np.concatenate([audio_array[start:end] for start, end in intervals])
        return non_silent_audio

    def _reduce_noise(self, audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply noise reduction to audio"""
        if not LIBROSA_AVAILABLE:
            # Simple noise reduction by spectral gating (basic implementation)
            # In practice, you'd want to use a more sophisticated method
            return audio_array  # For now, return as-is

        # Use librosa for noise reduction
        # This is a simplified approach - in practice, you might want to estimate
        # the noise profile separately
        try:
            # Simple spectral gating approach
            stft = librosa.stft(audio_array)
            magnitude = np.abs(stft)
            phase = np.angle(stft)

            # Estimate noise floor (simplified)
            noise_floor = np.mean(magnitude) * self.config.noise_reduction_strength

            # Apply spectral gate
            magnitude_reduced = np.maximum(magnitude - noise_floor, 0)

            # Reconstruct audio
            stft_reduced = magnitude_reduced * np.exp(1j * phase)
            audio_reduced = librosa.istft(stft_reduced)

            return audio_reduced.astype(audio_array.dtype)
        except Exception as e:
            self.logger.warning(f"Error in noise reduction: {e}, returning original audio")
            return audio_array

    def _calculate_rms(self, audio_array: np.ndarray) -> float:
        """Calculate root mean square energy of audio"""
        if len(audio_array) == 0:
            return 0.0
        return np.sqrt(np.mean(audio_array ** 2))

    def validate_audio_quality(self, audio_data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate audio quality based on preprocessing results

        Args:
            audio_data: Result from preprocess_audio method

        Returns:
            Dictionary with validation results
        """
        duration = audio_data.get('duration', 0)
        rms = audio_data.get('rms', 0)
        processed_audio = audio_data.get('processed_audio', np.array([]))

        validation_results = {
            'valid_duration': duration > 0.1 and duration < 30,  # 0.1s to 30s range
            'adequate_volume': rms > 0.001,  # Minimum volume threshold
            'not_empty': len(processed_audio) > 0,
            'sufficient_samples': len(processed_audio) > 1000  # At least 1000 samples
        }

        all_valid = all(validation_results.values())

        if all_valid:
            self.logger.info("Audio quality validation passed", extra=validation_results)
        else:
            self.logger.warning("Audio quality validation failed", extra=validation_results)

        return validation_results


class StreamingAudioProcessor:
    """
    Audio processor for streaming audio data
    Processes audio in chunks for real-time applications
    """

    def __init__(self, config: Optional[AudioProcessorConfig] = None):
        self.config = config or AudioProcessorConfig()
        self.logger = logging.getLogger(__name__)
        self.audio_processor = AudioProcessor(config)
        self.buffer = np.array([])
        self.processed_chunks = []

    async def add_audio_chunk(self, chunk: Union[bytes, np.ndarray], sample_rate: int) -> bool:
        """
        Add an audio chunk to the processing buffer

        Args:
            chunk: Audio chunk as bytes or numpy array
            sample_rate: Sample rate of the chunk

        Returns:
            True if chunk was added successfully
        """
        try:
            if isinstance(chunk, bytes):
                # Convert bytes to numpy array
                chunk_array = await self.audio_processor._load_audio_bytes(chunk, sample_rate)
            else:
                chunk_array = chunk

            # Append to buffer
            self.buffer = np.concatenate([self.buffer, chunk_array]) if len(self.buffer) > 0 else chunk_array

            return True
        except Exception as e:
            self.logger.error(f"Error adding audio chunk: {e}")
            return False

    async def process_buffer(self, min_duration: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Process the accumulated audio buffer if it meets minimum duration

        Args:
            min_duration: Minimum duration in seconds to process

        Returns:
            Preprocessing result if buffer is long enough, None otherwise
        """
        if len(self.buffer) == 0:
            return None

        current_duration = len(self.buffer) / self.config.target_sample_rate

        if current_duration < min_duration:
            return None

        # Process the buffer
        try:
            result = await self.audio_processor.preprocess_audio(
                self.buffer,
                sample_rate=self.config.target_sample_rate
            )

            # Clear the buffer after processing
            self.buffer = np.array([])

            return result
        except Exception as e:
            self.logger.error(f"Error processing audio buffer: {e}")
            return None

    def reset(self):
        """Reset the streaming processor"""
        self.buffer = np.array([])
        self.processed_chunks = []


# Utility functions for audio processing
def estimate_audio_duration(audio_data: Union[bytes, np.ndarray], sample_rate: int) -> float:
    """
    Estimate duration of audio data

    Args:
        audio_data: Audio data as bytes or numpy array
        sample_rate: Sample rate in Hz

    Returns:
        Duration in seconds
    """
    if isinstance(audio_data, np.ndarray):
        num_samples = len(audio_data)
    elif isinstance(audio_data, bytes):
        # Assume 16-bit PCM
        num_samples = len(audio_data) // 2
    else:
        raise ValueError(f"Unsupported audio data type: {type(audio_data)}")

    return num_samples / sample_rate


def detect_silence_regions(audio_array: np.ndarray, sample_rate: int,
                          threshold: float = 0.01, min_duration: float = 0.1) -> list:
    """
    Detect silence regions in audio

    Args:
        audio_array: Audio as numpy array
        sample_rate: Sample rate in Hz
        threshold: Amplitude threshold for silence
        min_duration: Minimum duration for a region to be considered silence

    Returns:
        List of (start_time, end_time) tuples for silence regions
    """
    if not LIBROSA_AVAILABLE:
        # Simple silence detection based on amplitude
        silent_samples = np.where(np.abs(audio_array) <= threshold)[0]
        min_samples = int(min_duration * sample_rate)

        silence_regions = []
        current_start = None

        for i in range(len(silent_samples)):
            if current_start is None:
                current_start = silent_samples[i]
            elif silent_samples[i] != silent_samples[i-1] + 1:
                # Gap in silence, end current region
                if silent_samples[i-1] - current_start >= min_samples:
                    start_time = current_start / sample_rate
                    end_time = silent_samples[i-1] / sample_rate
                    silence_regions.append((start_time, end_time))
                current_start = silent_samples[i]

        # Handle the last region
        if current_start is not None and len(silent_samples) > 0:
            if silent_samples[-1] - current_start >= min_samples:
                start_time = current_start / sample_rate
                end_time = silent_samples[-1] / sample_rate
                silence_regions.append((start_time, end_time))

        return silence_regions

    # Use librosa for more sophisticated silence detection
    intervals = librosa.effects.split(
        audio_array,
        top_db=-20 * np.log10(threshold),
        frame_length=2048,
        hop_length=512
    )

    # Convert intervals to silence regions
    silence_regions = []
    prev_end = 0

    for start, end in intervals:
        if start > prev_end:
            # There's a silence region between prev_end and start
            silence_start = prev_end / sample_rate
            silence_end = start / sample_rate
            if silence_end - silence_start >= min_duration:
                silence_regions.append((silence_start, silence_end))
        prev_end = end

    # Check for silence at the end
    total_length = len(audio_array)
    if prev_end < total_length:
        silence_start = prev_end / sample_rate
        silence_end = total_length / sample_rate
        if silence_end - silence_start >= min_duration:
            silence_regions.append((silence_start, silence_end))

    return silence_regions


async def main():
    """Example usage of audio processor"""
    import sys

    # Check if required libraries are available
    if not LIBROSA_AVAILABLE:
        print("Warning: librosa not available - limited preprocessing capabilities")
        print("Install with: pip install librosa")

    # Initialize audio processor
    config = AudioProcessorConfig(
        target_sample_rate=16000,
        normalize_audio=True,
        remove_silence=True,
        noise_reduction=True
    )
    processor = AudioProcessor(config)

    print("Audio processor initialized with configuration:")
    print(f"  Target sample rate: {config.target_sample_rate} Hz")
    print(f"  Normalize audio: {config.normalize_audio}")
    print(f"  Remove silence: {config.remove_silence}")
    print(f"  Noise reduction: {config.noise_reduction}")

    # Example would require actual audio data to process
    print("\nAudio processor ready for use with the VLA system.")


if __name__ == "__main__":
    asyncio.run(main())