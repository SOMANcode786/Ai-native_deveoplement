"""
Microphone Input Handling for Vision-Language-Action (VLA) System

This module provides functionality for capturing audio from microphone input
for use with the VLA system's speech recognition capabilities.
"""

import asyncio
import threading
import queue
import time
import logging
from typing import Optional, Callable, Dict, Any, AsyncGenerator
from dataclasses import dataclass

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    pyaudio = None

try:
    import sounddevice as sd
    import numpy as np
    SOUNDD_DEVICE_AVAILABLE = True
except ImportError:
    SOUNDD_DEVICE_AVAILABLE = False
    sd = None
    np = None


@dataclass
class AudioConfig:
    """Configuration for audio input"""
    sample_rate: int = 16000
    chunk_size: int = 1024
    channels: int = 1
    format: int = 8  # pyaudio.paInt16
    device_index: Optional[int] = None
    input_timeout: float = 5.0  # seconds


class MicrophoneInput:
    """
    Microphone input handler for capturing audio in real-time
    Supports both PyAudio and SoundDevice backends
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.logger = logging.getLogger(__name__)
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.recording_thread = None

        # Determine which backend to use
        if SOUNDD_DEVICE_AVAILABLE:
            self.backend = "sounddevice"
            self._init_sounddevice()
        elif PYAUDIO_AVAILABLE:
            self.backend = "pyaudio"
            self._init_pyaudio()
        else:
            raise RuntimeError("Neither pyaudio nor sounddevice is available for audio input")

    def _init_sounddevice(self):
        """Initialize with sounddevice backend"""
        if not SOUNDD_DEVICE_AVAILABLE:
            raise RuntimeError("SoundDevice not available")

        self.logger.info("Initialized microphone input with SoundDevice backend")
        # Verify audio device is available
        devices = sd.query_devices()
        if self.config.device_index is not None:
            if self.config.device_index >= len(devices):
                raise ValueError(f"Device index {self.config.device_index} not available")
            device_info = devices[self.config.device_index]
            if not device_info['max_input_channels'] > 0:
                raise ValueError(f"Device {self.config.device_index} is not an input device")
        else:
            # Find default input device
            default_input = sd.query_devices(kind='input')
            self.logger.info(f"Default input device: {default_input}")

    def _init_pyaudio(self):
        """Initialize with PyAudio backend"""
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio not available")

        self.pyaudio_instance = pyaudio.PyAudio()
        self.logger.info("Initialized microphone input with PyAudio backend")

        # Verify audio device is available
        if self.config.device_index is not None:
            if self.config.device_index >= self.pyaudio_instance.get_device_count():
                raise ValueError(f"Device index {self.config.device_index} not available")
        else:
            # Use default input device
            self.config.device_index = self.pyaudio_instance.get_default_input_device_info()['index']

    def start_recording(self):
        """Start recording audio from microphone"""
        if self.is_recording:
            self.logger.warning("Recording already in progress")
            return

        self.is_recording = True
        self.recording_thread = threading.Thread(target=self._record_audio)
        self.recording_thread.start()
        self.logger.info("Started microphone recording")

    def stop_recording(self):
        """Stop recording audio from microphone"""
        if not self.is_recording:
            self.logger.warning("No recording in progress")
            return

        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join()
        self.logger.info("Stopped microphone recording")

    def _record_audio(self):
        """Internal method to record audio in a separate thread"""
        if self.backend == "sounddevice":
            self._record_with_sounddevice()
        elif self.backend == "pyaudio":
            self._record_with_pyaudio()

    def _record_with_sounddevice(self):
        """Record audio using SoundDevice backend"""
        if not SOUNDD_DEVICE_AVAILABLE:
            raise RuntimeError("SoundDevice not available")

        def audio_callback(indata, frames, time, status):
            if status:
                self.logger.warning(f"Audio callback status: {status}")
            # Add audio data to queue
            audio_data = indata.copy()
            try:
                self.audio_queue.put_nowait(audio_data)
            except queue.Full:
                # Queue is full, drop the data
                pass

        try:
            with sd.InputStream(
                callback=audio_callback,
                channels=self.config.channels,
                samplerate=self.config.sample_rate,
                dtype=np.float32,
                blocksize=self.config.chunk_size,
                device=self.config.device_index
            ):
                while self.is_recording:
                    time.sleep(0.01)  # Small sleep to prevent busy waiting
        except Exception as e:
            self.logger.error(f"Error in SoundDevice recording: {e}")
            self.is_recording = False

    def _record_with_pyaudio(self):
        """Record audio using PyAudio backend"""
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio not available")

        try:
            stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
                input_device_index=self.config.device_index
            )

            while self.is_recording:
                data = stream.read(self.config.chunk_size, exception_on_overflow=False)
                try:
                    self.audio_queue.put_nowait(data)
                except queue.Full:
                    # Queue is full, drop the data
                    pass

            stream.stop_stream()
            stream.close()
        except Exception as e:
            self.logger.error(f"Error in PyAudio recording: {e}")
            self.is_recording = False

    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[bytes]:
        """Get a single chunk of audio data from the queue"""
        try:
            chunk = self.audio_queue.get(timeout=timeout)
            if self.backend == "sounddevice" and SOUNDD_DEVICE_AVAILABLE:
                # Convert numpy array to bytes
                import io
                import wave
                # Convert float32 to int16
                chunk_int16 = (chunk * 32767).astype(np.int16)
                return chunk_int16.tobytes()
            else:
                return chunk
        except queue.Empty:
            return None

    async def get_audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Get audio as an async generator for streaming"""
        while self.is_recording:
            chunk = self.get_audio_chunk(timeout=0.1)
            if chunk:
                yield chunk
            else:
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.01)

    def is_audio_available(self) -> bool:
        """Check if audio data is available in the queue"""
        return not self.audio_queue.empty()

    def clear_audio_queue(self):
        """Clear all audio data from the queue"""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def get_device_info(self) -> Dict[str, Any]:
        """Get information about the audio input device"""
        info = {
            'backend': self.backend,
            'sample_rate': self.config.sample_rate,
            'channels': self.config.channels,
            'chunk_size': self.config.chunk_size
        }

        if self.backend == "sounddevice" and SOUNDD_DEVICE_AVAILABLE:
            devices = sd.query_devices()
            if self.config.device_index is not None:
                info['device_info'] = devices[self.config.device_index]
        elif self.backend == "pyaudio" and PYAUDIO_AVAILABLE:
            if self.config.device_index is not None:
                info['device_info'] = self.pyaudio_instance.get_device_info_by_index(self.config.device_index)

        return info


class AudioInputManager:
    """
    Manager class for handling multiple audio input sources
    Provides high-level interface for audio capture and processing
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.microphone = None
        self.logger = logging.getLogger(__name__)
        self.active_listeners = []

    async def initialize_microphone(self):
        """Initialize the microphone input"""
        try:
            self.microphone = MicrophoneInput(self.config)
            self.logger.info("Microphone initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize microphone: {e}")
            return False

    async def start_listening(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Start listening for audio and return captured audio data
        If timeout is specified, listen for that duration
        Otherwise, listen until silence is detected or stopped manually
        """
        if not self.microphone:
            await self.initialize_microphone()
            if not self.microphone:
                raise RuntimeError("Failed to initialize microphone")

        self.microphone.start_recording()

        try:
            start_time = time.time()
            audio_chunks = []

            while self.microphone.is_recording:
                if timeout and (time.time() - start_time) > timeout:
                    break

                chunk = self.microphone.get_audio_chunk(timeout=0.1)
                if chunk:
                    audio_chunks.append(chunk)
                else:
                    # Check if we should stop based on silence detection
                    # For now, just continue until timeout or manual stop
                    pass

            # Combine all chunks into single audio data
            if audio_chunks:
                combined_audio = b''.join(audio_chunks)
                self.logger.info(f"Captured {len(combined_audio)} bytes of audio")
                return combined_audio
            else:
                self.logger.warning("No audio data captured")
                return None

        finally:
            self.microphone.stop_recording()
            self.microphone.clear_audio_queue()

    async def continuous_listening(self, callback: Callable[[bytes], None]):
        """
        Continuously listen for audio and call the callback with captured audio
        """
        if not self.microphone:
            await self.initialize_microphone()
            if not self.microphone:
                raise RuntimeError("Failed to initialize microphone")

        self.microphone.start_recording()
        self.active_listeners.append(callback)

        try:
            while self.microphone.is_recording:
                chunk = self.microphone.get_audio_chunk(timeout=0.1)
                if chunk:
                    # Call all registered callbacks
                    for listener in self.active_listeners:
                        try:
                            listener(chunk)
                        except Exception as e:
                            self.logger.error(f"Error in audio callback: {e}")

        finally:
            self.microphone.stop_recording()
            if callback in self.active_listeners:
                self.active_listeners.remove(callback)

    async def record_speech_command(self, max_duration: float = 10.0) -> Optional[bytes]:
        """
        Record a speech command with automatic silence detection
        """
        if not self.microphone:
            await self.initialize_microphone()
            if not self.microphone:
                raise RuntimeError("Failed to initialize microphone")

        self.microphone.start_recording()

        try:
            start_time = time.time()
            audio_chunks = []
            silence_start = None
            silence_threshold = 0.01  # Adjust based on your needs
            silence_duration_threshold = 1.0  # seconds of silence to stop

            while self.microphone.is_recording:
                if time.time() - start_time > max_duration:
                    self.logger.info("Maximum recording duration reached")
                    break

                chunk = self.microphone.get_audio_chunk(timeout=0.1)
                if chunk:
                    audio_chunks.append(chunk)

                    # Check if this chunk contains significant audio (not silence)
                    if self._is_silence(chunk):
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > silence_duration_threshold:
                            self.logger.info("Silence detected, stopping recording")
                            break
                    else:
                        # Reset silence timer if we detect audio
                        silence_start = None
                else:
                    # No chunk available, continue
                    pass

            if audio_chunks:
                combined_audio = b''.join(audio_chunks)
                self.logger.info(f"Recorded speech command: {len(combined_audio)} bytes")
                return combined_audio
            else:
                self.logger.warning("No speech command recorded")
                return None

        finally:
            self.microphone.stop_recording()
            self.microphone.clear_audio_queue()

    def _is_silence(self, audio_chunk: bytes) -> bool:
        """
        Simple silence detection based on audio amplitude
        """
        if not audio_chunk:
            return True

        # Convert bytes to numerical values for analysis
        # This is a simplified approach - in practice, use proper audio analysis
        if self.backend == "pyaudio":
            # PyAudio typically uses 16-bit integers
            import struct
            values = struct.unpack(f'{len(audio_chunk)//2}h', audio_chunk)
            avg_amplitude = sum(abs(v) for v in values) / len(values)
        else:
            # For other backends, use a simple approach
            avg_amplitude = sum(audio_chunk) / len(audio_chunk) if audio_chunk else 0

        return avg_amplitude < 500  # Threshold may need adjustment

    def get_available_devices(self) -> list:
        """Get list of available audio input devices"""
        if SOUNDD_DEVICE_AVAILABLE:
            devices = sd.query_devices()
            input_devices = []
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': device['name'],
                        'max_input_channels': device['max_input_channels'],
                        'default_samplerate': device['default_samplerate']
                    })
            return input_devices
        elif PYAUDIO_AVAILABLE:
            input_devices = []
            for i in range(self.pyaudio_instance.get_device_count()):
                info = self.pyaudio_instance.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': info['name'],
                        'max_input_channels': info['maxInputChannels'],
                        'default_samplerate': info['defaultSampleRate']
                    })
            return input_devices
        else:
            return []


# Utility functions for audio processing
def get_microphone_levels(audio_data: bytes) -> Dict[str, float]:
    """
    Get audio level information from audio data
    """
    if not audio_data:
        return {'rms': 0.0, 'peak': 0.0, 'db': -float('inf')}

    import struct
    # Assume 16-bit audio data
    values = struct.unpack(f'{len(audio_data)//2}h', audio_data)

    # Calculate RMS (Root Mean Square)
    sum_squares = sum(v * v for v in values)
    rms = (sum_squares / len(values)) ** 0.5

    # Calculate peak amplitude
    peak = max(abs(v) for v in values)

    # Calculate dB level (relative to max possible amplitude for 16-bit)
    max_possible = 32767
    db = 20 * (rms / max_possible) if rms > 0 else -float('inf')

    return {
        'rms': rms,
        'peak': peak,
        'db': db
    }


async def test_microphone():
    """Test function for microphone input"""
    print("Testing microphone input...")

    # Check if required libraries are available
    if not PYAUDIO_AVAILABLE and not SOUNDD_DEVICE_AVAILABLE:
        print("Error: Neither pyaudio nor sounddevice is available")
        print("Install with: pip install pyaudio or pip install sounddevice")
        return False

    # Initialize audio input manager
    config = AudioConfig(sample_rate=16000, channels=1)
    audio_manager = AudioInputManager(config)

    try:
        # Initialize microphone
        success = await audio_manager.initialize_microphone()
        if not success:
            print("Failed to initialize microphone")
            return False

        # Show available devices
        devices = audio_manager.get_available_devices()
        print(f"Available input devices: {len(devices)}")
        for device in devices:
            print(f"  {device['index']}: {device['name']}")

        # Test recording a short command
        print("\nPlease speak a command now (recording for 5 seconds)...")
        audio_data = await audio_manager.start_listening(timeout=5.0)

        if audio_data:
            print(f"Successfully recorded {len(audio_data)} bytes of audio")
            levels = get_microphone_levels(audio_data)
            print(f"Audio levels - RMS: {levels['rms']:.2f}, Peak: {levels['peak']:.2f}, dB: {levels['db']:.2f}")
        else:
            print("No audio data recorded")

        return True

    except Exception as e:
        print(f"Error testing microphone: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_microphone())