"""
Audio Input Error Handling for Vision-Language-Action (VLA) System

This module provides comprehensive error handling for audio input failures
in the VLA system's speech recognition pipeline.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from src.error_handling import VLAException, VLAErrorType, ErrorHandler, VLALogger


class AudioErrorType(Enum):
    """Specific error types for audio input"""
    MICROPHONE_ACCESS_DENIED = "microphone_access_denied"
    MICROPHONE_NOT_FOUND = "microphone_not_found"
    AUDIO_DEVICE_BUSY = "audio_device_busy"
    SAMPLE_RATE_MISMATCH = "sample_rate_mismatch"
    AUDIO_FORMAT_UNSUPPORTED = "audio_format_unsupported"
    RECORDING_TIMEOUT = "recording_timeout"
    AUDIO_LEVEL_TOO_LOW = "audio_level_too_low"
    AUDIO_LEVEL_TOO_HIGH = "audio_level_too_high"
    NO_AUDIO_DETECTED = "no_audio_detected"
    AUDIO_CLIP_DETECTED = "audio_clipping_detected"
    BUFFER_OVERFLOW = "buffer_overflow"
    DRIVER_ERROR = "driver_error"


@dataclass
class AudioError:
    """Audio-specific error information"""
    error_type: AudioErrorType
    device_info: Optional[Dict[str, Any]] = None
    audio_level: Optional[float] = None
    sample_rate: Optional[int] = None
    duration: Optional[float] = None


class AudioErrorHandler:
    """Specialized error handler for audio input issues"""

    def __init__(self, logger: Optional[VLALogger] = None, error_handler: Optional[ErrorHandler] = None):
        self.logger = logger or VLALogger("AudioErrorHandler")
        self.error_handler = error_handler or ErrorHandler(self.logger)
        self.error_recovery_strategies: Dict[AudioErrorType, Callable] = {}
        self.error_history: List[AudioError] = []

    def register_recovery_strategy(self, error_type: AudioErrorType, strategy: Callable):
        """Register a recovery strategy for a specific error type"""
        self.error_recovery_strategies[error_type] = strategy

    def handle_audio_error(self, error_type: AudioErrorType, component: str,
                          device_info: Optional[Dict[str, Any]] = None,
                          audio_level: Optional[float] = None,
                          sample_rate: Optional[int] = None,
                          duration: Optional[float] = None,
                          should_raise: bool = True) -> Optional[AudioError]:
        """Handle a specific audio error"""
        try:
            audio_error = AudioError(
                error_type=error_type,
                device_info=device_info,
                audio_level=audio_level,
                sample_rate=sample_rate,
                duration=duration
            )

            # Log the error
            error_msg = f"Audio error [{error_type.value}] in {component}"
            if audio_level is not None:
                error_msg += f", level: {audio_level:.4f}"
            if sample_rate is not None:
                error_msg += f", rate: {sample_rate}Hz"

            self.logger.error(error_msg, component=component)

            # Add to history
            self.error_history.append(audio_error)

            # Apply recovery strategy if registered
            if error_type in self.error_recovery_strategies:
                try:
                    recovery_result = self.error_recovery_strategies[error_type](audio_error)
                    self.logger.info(f"Applied recovery strategy for {error_type.value}: {recovery_result}", component=component)
                except Exception as recovery_error:
                    self.logger.error(f"Recovery strategy failed for {error_type.value}: {recovery_error}", component=component)

            # Handle with main error handler
            vla_error = VLAException(
                error_type=self._map_to_vla_error_type(error_type),
                message=f"Audio error: {error_type.value}",
                component=component,
                details={
                    "audio_error_type": error_type.value,
                    "device_info": device_info,
                    "audio_level": audio_level,
                    "sample_rate": sample_rate,
                    "duration": duration
                }
            )

            if should_raise:
                self.error_handler.handle_error(vla_error, should_raise=True)
            else:
                self.error_handler.handle_error(vla_error, should_raise=False)

            return audio_error

        except Exception as e:
            self.logger.error(f"Error in audio error handling: {e}", component="AudioErrorHandler")
            return None

    def _map_to_vla_error_type(self, audio_error_type: AudioErrorType) -> VLAErrorType:
        """Map audio error types to VLA error types"""
        mapping = {
            AudioErrorType.MICROPHONE_ACCESS_DENIED: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.MICROPHONE_NOT_FOUND: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.AUDIO_DEVICE_BUSY: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.SAMPLE_RATE_MISMATCH: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.AUDIO_FORMAT_UNSUPPORTED: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.RECORDING_TIMEOUT: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.AUDIO_LEVEL_TOO_LOW: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.AUDIO_LEVEL_TOO_HIGH: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.NO_AUDIO_DETECTED: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.AUDIO_CLIP_DETECTED: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.BUFFER_OVERFLOW: VLAErrorType.SPEECH_RECOGNITION_ERROR,
            AudioErrorType.DRIVER_ERROR: VLAErrorType.SPEECH_RECOGNITION_ERROR,
        }
        return mapping.get(audio_error_type, VLAErrorType.SPEECH_RECOGNITION_ERROR)

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get statistics about audio errors"""
        if not self.error_history:
            return {"total_errors": 0}

        error_counts = {}
        for error in self.error_history:
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return {
            "total_errors": len(self.error_history),
            "error_counts": error_counts,
            "recent_errors": [err.error_type.value for err in self.error_history[-10:]]  # Last 10 errors
        }

    def reset_error_history(self):
        """Reset the error history"""
        self.error_history = []


class AudioInputValidator:
    """Validates audio input quality and detects potential issues"""

    def __init__(self, error_handler: Optional[AudioErrorHandler] = None):
        self.error_handler = error_handler or AudioErrorHandler()
        self.logger = VLALogger("AudioInputValidator")

    def validate_audio_device(self, device_info: Dict[str, Any], component: str) -> bool:
        """Validate that an audio device is properly configured"""
        try:
            # Check if device has input channels
            max_input_channels = device_info.get('max_input_channels', 0)
            if max_input_channels <= 0:
                self.error_handler.handle_audio_error(
                    AudioErrorType.MICROPHONE_NOT_FOUND,
                    component,
                    device_info=device_info
                )
                return False

            # Check sample rate support
            default_sample_rate = device_info.get('default_samplerate', 0)
            if default_sample_rate <= 8000:  # Too low for speech recognition
                self.error_handler.handle_audio_error(
                    AudioErrorType.SAMPLE_RATE_MISMATCH,
                    component,
                    device_info=device_info,
                    sample_rate=int(default_sample_rate)
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating audio device: {e}", component=component)
            return False

    def validate_audio_level(self, audio_data: bytes, component: str,
                           min_level: float = 0.001, max_level: float = 0.9) -> bool:
        """Validate that audio level is within acceptable range"""
        try:
            import struct
            # Calculate RMS level
            values = struct.unpack(f'{len(audio_data)//2}h', audio_data)
            rms = (sum(v * v for v in values) / len(values)) ** 0.5
            # Normalize to 0-1 range (assuming 16-bit audio)
            normalized_rms = rms / 32767.0

            if normalized_rms < min_level:
                self.error_handler.handle_audio_error(
                    AudioErrorType.AUDIO_LEVEL_TOO_LOW,
                    component,
                    audio_level=normalized_rms
                )
                return False
            elif normalized_rms > max_level:
                self.error_handler.handle_audio_error(
                    AudioErrorType.AUDIO_LEVEL_TOO_HIGH,
                    component,
                    audio_level=normalized_rms
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating audio level: {e}", component=component)
            return False

    def validate_audio_duration(self, duration: float, min_duration: float, max_duration: float,
                              component: str) -> bool:
        """Validate that audio duration is within acceptable range"""
        try:
            if duration < min_duration:
                self.error_handler.handle_audio_error(
                    AudioErrorType.NO_AUDIO_DETECTED,
                    component,
                    duration=duration
                )
                return False
            elif duration > max_duration:
                self.error_handler.handle_audio_error(
                    AudioErrorType.RECORDING_TIMEOUT,
                    component,
                    duration=duration
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating audio duration: {e}", component=component)
            return False

    def detect_audio_issues(self, audio_data: bytes, sample_rate: int,
                           component: str) -> List[AudioErrorType]:
        """Detect potential issues with audio data"""
        issues = []

        try:
            import struct
            import numpy as np

            # Convert to numpy array for analysis
            values = struct.unpack(f'{len(audio_data)//2}h', audio_data)
            audio_array = np.array(values, dtype=np.float32) / 32767.0

            # Check for clipping (values at max/min)
            max_val = np.max(np.abs(audio_array))
            if max_val > 0.95:  # Close to maximum, possible clipping
                issues.append(AudioErrorType.AUDIO_CLIP_DETECTED)

            # Check for silence
            rms = np.sqrt(np.mean(audio_array ** 2))
            if rms < 0.001:  # Very quiet, might be silence
                issues.append(AudioErrorType.NO_AUDIO_DETECTED)

            # Check for consistent values (no variation might indicate no input)
            std_dev = np.std(audio_array)
            if std_dev < 0.0001:  # Very little variation
                issues.append(AudioErrorType.NO_AUDIO_DETECTED)

        except Exception as e:
            self.logger.error(f"Error detecting audio issues: {e}", component=component)

        return issues


class RobustAudioInput:
    """Wrapper for audio input with built-in error handling and recovery"""

    def __init__(self, audio_manager, error_handler: Optional[AudioErrorHandler] = None):
        self.audio_manager = audio_manager
        self.error_handler = error_handler or AudioErrorHandler()
        self.logger = VLALogger("RobustAudioInput")
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3

    async def safe_record_command(self, max_duration: float = 5.0,
                                retry_on_failure: bool = True) -> Optional[bytes]:
        """Safely record a speech command with error handling"""
        attempt = 0

        while attempt < (self.max_recovery_attempts if retry_on_failure else 1):
            try:
                self.logger.info(f"Recording command (attempt {attempt + 1})", component="RobustAudioInput")

                # Try to record audio
                audio_data = await self.audio_manager.record_speech_command(max_duration)

                if audio_data:
                    # Validate the recorded audio
                    validator = AudioInputValidator(self.error_handler)

                    # Check duration
                    duration = len(audio_data) / 16000  # Assuming 16kHz
                    if not validator.validate_audio_duration(duration, 0.1, max_duration, "RobustAudioInput"):
                        audio_data = None  # Mark as invalid
                    # Check audio level
                    elif not validator.validate_audio_level(audio_data, "RobustAudioInput"):
                        audio_data = None  # Mark as invalid

                    if audio_data:
                        # Check for other issues
                        issues = validator.detect_audio_issues(audio_data, 16000, "RobustAudioInput")
                        if issues:
                            self.logger.warning(f"Audio issues detected: {issues}", component="RobustAudioInput")

                if audio_data:
                    self.logger.info(f"Successfully recorded {len(audio_data)} bytes of audio", component="RobustAudioInput")
                    return audio_data
                else:
                    self.logger.warning(f"Attempt {attempt + 1} failed - no valid audio recorded", component="RobustAudioInput")

            except Exception as e:
                self.logger.error(f"Error in recording attempt {attempt + 1}: {e}", component="RobustAudioInput")
                self.error_handler.handle_audio_error(
                    AudioErrorType.DRIVER_ERROR,
                    "RobustAudioInput.safe_record_command",
                    should_raise=False
                )

            attempt += 1

            if attempt < (self.max_recovery_attempts if retry_on_failure else 1):
                # Wait before retrying
                await asyncio.sleep(0.5)

        self.logger.error("All recording attempts failed", component="RobustAudioInput")
        return None

    async def safe_initialize_microphone(self) -> bool:
        """Safely initialize microphone with error handling"""
        try:
            self.logger.info("Initializing microphone with error handling", component="RobustAudioInput")

            success = await self.audio_manager.initialize_microphone()

            if not success:
                self.error_handler.handle_audio_error(
                    AudioErrorType.MICROPHONE_ACCESS_DENIED,
                    "RobustAudioInput.safe_initialize_microphone"
                )
                return False

            # Validate available devices
            devices = self.audio_manager.get_available_devices()
            if not devices:
                self.error_handler.handle_audio_error(
                    AudioErrorType.MICROPHONE_NOT_FOUND,
                    "RobustAudioInput.safe_initialize_microphone"
                )
                return False

            # Validate the first device
            validator = AudioInputValidator(self.error_handler)
            if not validator.validate_audio_device(devices[0], "RobustAudioInput.safe_initialize_microphone"):
                return False

            self.logger.info(f"Microphone initialized successfully with {len(devices)} devices available", component="RobustAudioInput")
            return True

        except Exception as e:
            self.logger.error(f"Error initializing microphone: {e}", component="RobustAudioInput")
            self.error_handler.handle_audio_error(
                AudioErrorType.DRIVER_ERROR,
                "RobustAudioInput.safe_initialize_microphone"
            )
            return False


# Default error recovery strategies
def default_microphone_not_found_strategy(audio_error: AudioError) -> str:
    """Default strategy for when microphone is not found"""
    return "Check if microphone is connected and not being used by another application"


def default_microphone_access_denied_strategy(audio_error: AudioError) -> str:
    """Default strategy for when microphone access is denied"""
    return "Check application permissions for microphone access"


def default_audio_level_too_low_strategy(audio_error: AudioError) -> str:
    """Default strategy for when audio level is too low"""
    return "Ask user to speak louder or move closer to microphone"


def default_audio_level_too_high_strategy(audio_error: AudioError) -> str:
    """Default strategy for when audio level is too high"""
    return "Ask user to speak softer or move farther from microphone"


def default_recording_timeout_strategy(audio_error: AudioError) -> str:
    """Default strategy for when recording times out"""
    return "Extend recording timeout or prompt user to speak"


def setup_default_recovery_strategies(error_handler: AudioErrorHandler):
    """Setup default recovery strategies for common audio errors"""
    strategies = {
        AudioErrorType.MICROPHONE_NOT_FOUND: default_microphone_not_found_strategy,
        AudioErrorType.MICROPHONE_ACCESS_DENIED: default_microphone_access_denied_strategy,
        AudioErrorType.AUDIO_LEVEL_TOO_LOW: default_audio_level_too_low_strategy,
        AudioErrorType.AUDIO_LEVEL_TOO_HIGH: default_audio_level_too_high_strategy,
        AudioErrorType.RECORDING_TIMEOUT: default_recording_timeout_strategy,
    }

    for error_type, strategy in strategies.items():
        error_handler.register_recovery_strategy(error_type, strategy)


# Example usage and testing
async def test_audio_error_handling():
    """Test function for audio error handling"""
    print("Testing Audio Error Handling...")

    # Create error handler
    audio_error_handler = AudioErrorHandler()
    setup_default_recovery_strategies(audio_error_handler)

    # Test different error scenarios
    print("\n1. Testing microphone not found error...")
    audio_error_handler.handle_audio_error(
        AudioErrorType.MICROPHONE_NOT_FOUND,
        "TestComponent",
        device_info={"name": "Test Device", "index": 0}
    )

    print("\n2. Testing audio level too low error...")
    audio_error_handler.handle_audio_error(
        AudioErrorType.AUDIO_LEVEL_TOO_LOW,
        "TestComponent",
        audio_level=0.0001
    )

    print("\n3. Testing recording timeout error...")
    audio_error_handler.handle_audio_error(
        AudioErrorType.RECORDING_TIMEOUT,
        "TestComponent",
        duration=10.0
    )

    # Show error statistics
    stats = audio_error_handler.get_error_statistics()
    print(f"\n4. Error Statistics:")
    print(f"   Total errors: {stats['total_errors']}")
    print(f"   Error types: {list(stats['error_counts'].keys())}")

    print("\nAudio error handling test completed.")


if __name__ == "__main__":
    asyncio.run(test_audio_error_handling())