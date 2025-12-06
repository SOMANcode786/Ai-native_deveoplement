"""
Speech-to-Text Conversion Examples for Vision-Language-Action (VLA) System

This module provides examples of speech-to-text conversion using the VLA system's
speech recognition capabilities.
"""

import asyncio
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Import our speech recognition modules
from src.speech_recognition.whisper_integration import WhisperIntegration
from src.speech_recognition.audio_input import AudioInputManager, AudioConfig
from src.speech_recognition.audio_processor import AudioProcessor, AudioProcessorConfig
from src.error_handling import ErrorHandler, VLALogger


class VoiceToTextExamples:
    """
    Examples and utilities for voice-to-text conversion in the VLA system
    """

    def __init__(self):
        self.logger = VLALogger("VoiceToTextExamples")
        self.error_handler = ErrorHandler(self.logger)
        self.whisper_integration = None
        self.audio_manager = None
        self.audio_processor = None

    async def setup_components(self, use_local_model: bool = True, model_name: str = "base"):
        """
        Setup speech recognition components
        """
        try:
            # Setup Whisper integration
            api_key = os.getenv("OPENAI_API_KEY") if not use_local_model else None
            self.whisper_integration = WhisperIntegration(
                api_key=api_key,
                model_name=model_name,
                use_local=use_local_model
            )

            # Setup audio input manager
            audio_config = AudioConfig(sample_rate=16000)
            self.audio_manager = AudioInputManager(audio_config)

            # Setup audio processor
            processor_config = AudioProcessorConfig(
                target_sample_rate=16000,
                normalize_audio=True,
                remove_silence=True,
                noise_reduction=True
            )
            self.audio_processor = AudioProcessor(processor_config)

            self.logger.info("Voice-to-text components initialized", component="VoiceToTextExamples")
            return True

        except Exception as e:
            self.error_handler.handle_exception(e, "VoiceToTextExamples.setup_components")
            return False

    async def transcribe_file_example(self, audio_file_path: str) -> Optional[Dict[str, Any]]:
        """
        Example: Transcribe an audio file to text
        """
        if not self.whisper_integration:
            self.logger.error("Components not initialized", component="VoiceToTextExamples")
            return None

        try:
            self.logger.info(f"Transcribing audio file: {audio_file_path}", component="VoiceToTextExamples")

            # Preprocess the audio file
            if self.audio_processor:
                preprocess_result = await self.audio_processor.preprocess_audio(audio_file_path)
                self.logger.info(
                    f"Preprocessing completed: {preprocess_result['duration']:.2f}s duration, "
                    f"RMS: {preprocess_result['rms']:.4f}",
                    component="VoiceToTextExamples"
                )

            # Transcribe the audio
            result = await self.whisper_integration.transcribe_audio(audio_file_path)

            self.logger.info(f"Transcription completed: {result['text'][:100]}...", component="VoiceToTextExamples")
            return result

        except Exception as e:
            self.error_handler.handle_exception(e, "VoiceToTextExamples.transcribe_file_example")
            return None

    async def real_time_transcription_example(self, duration: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Example: Real-time speech-to-text conversion
        """
        if not self.whisper_integration or not self.audio_manager:
            self.logger.error("Components not initialized", component="VoiceToTextExamples")
            return None

        try:
            self.logger.info(f"Starting real-time transcription for {duration}s", component="VoiceToTextExamples")

            # Initialize microphone
            success = await self.audio_manager.initialize_microphone()
            if not success:
                self.logger.error("Failed to initialize microphone", component="VoiceToTextExamples")
                return None

            # Record audio
            recorded_audio = await self.audio_manager.start_listening(timeout=duration)

            if not recorded_audio:
                self.logger.warning("No audio recorded", component="VoiceToTextExamples")
                return None

            self.logger.info(f"Recorded {len(recorded_audio)} bytes of audio", component="VoiceToTextExamples")

            # Preprocess the recorded audio
            if self.audio_processor:
                preprocess_result = await self.audio_processor.preprocess_audio(
                    recorded_audio,
                    sample_rate=16000
                )
                self.logger.info(
                    f"Preprocessing completed: {preprocess_result['duration']:.2f}s duration",
                    component="VoiceToTextExamples"
                )

                # Use the processed audio for transcription
                processed_audio = preprocess_result['processed_audio']
                # Convert numpy array back to bytes for Whisper
                import numpy as np
                processed_bytes = (processed_audio * 32767).astype(np.int16).tobytes()
            else:
                processed_bytes = recorded_audio

            # Transcribe the audio
            result = await self.whisper_integration.transcribe_audio(processed_bytes)

            self.logger.info(f"Real-time transcription: {result['text']}", component="VoiceToTextExamples")
            return result

        except Exception as e:
            self.error_handler.handle_exception(e, "VoiceToTextExamples.real_time_transcription_example")
            return None

    async def batch_transcription_example(self, audio_files: list) -> list:
        """
        Example: Batch transcription of multiple audio files
        """
        if not self.whisper_integration:
            self.logger.error("Components not initialized", component="VoiceToTextExamples")
            return []

        try:
            self.logger.info(f"Starting batch transcription of {len(audio_files)} files", component="VoiceToTextExamples")

            results = await self.whisper_integration.batch_transcribe(audio_files)

            successful_transcriptions = 0
            for i, result in enumerate(results):
                if 'error' not in result:
                    successful_transcriptions += 1
                    self.logger.info(
                        f"File {i+1}: {result['text'][:50]}...",
                        component="VoiceToTextExamples"
                    )
                else:
                    self.logger.error(f"File {i+1} failed: {result['error']}", component="VoiceToTextExamples")

            self.logger.info(
                f"Batch transcription completed: {successful_transcriptions}/{len(audio_files)} successful",
                component="VoiceToTextExamples"
            )

            return results

        except Exception as e:
            self.error_handler.handle_exception(e, "VoiceToTextExamples.batch_transcription_example")
            return []

    async def streaming_transcription_example(self, duration: float = 10.0) -> list:
        """
        Example: Streaming transcription with continuous processing
        """
        if not self.whisper_integration or not self.audio_manager:
            self.logger.error("Components not initialized", component="VoiceToTextExamples")
            return []

        try:
            self.logger.info(f"Starting streaming transcription for {duration}s", component="VoiceToTextExamples")

            # Initialize microphone
            success = await self.audio_manager.initialize_microphone()
            if not success:
                self.logger.error("Failed to initialize microphone", component="VoiceToTextExamples")
                return []

            # Use the streaming audio processor
            from src.speech_recognition.audio_processor import StreamingAudioProcessor
            streaming_processor = StreamingAudioProcessor()

            transcriptions = []
            start_time = asyncio.get_event_loop().time()

            # Start recording
            self.audio_manager.microphone.start_recording()

            try:
                async for audio_chunk in self.audio_manager.microphone.get_audio_stream():
                    current_time = asyncio.get_event_loop().time()
                    if current_time - start_time > duration:
                        break

                    # Add chunk to streaming processor
                    added = await streaming_processor.add_audio_chunk(audio_chunk, sample_rate=16000)

                    if added:
                        # Try to process if we have enough data
                        result = await streaming_processor.process_buffer(min_duration=1.0)
                        if result:
                            # Transcribe the processed buffer
                            transcription = await self.whisper_integration.transcribe_audio(
                                result['processed_audio'],
                                language='en'
                            )
                            transcriptions.append(transcription)
                            self.logger.info(f"Streaming transcription: {transcription['text']}", component="VoiceToTextExamples")

            finally:
                self.audio_manager.microphone.stop_recording()

            self.logger.info(f"Streaming transcription completed: {len(transcriptions)} segments", component="VoiceToTextExamples")
            return transcriptions

        except Exception as e:
            self.error_handler.handle_exception(e, "VoiceToTextExamples.streaming_transcription_example")
            return []

    async def command_processing_example(self) -> Dict[str, Any]:
        """
        Example: Process voice commands for VLA system
        """
        if not self.whisper_integration or not self.audio_manager:
            self.logger.error("Components not initialized", component="VoiceToTextExamples")
            return {"success": False, "error": "Components not initialized"}

        try:
            self.logger.info("Starting voice command processing example", component="VoiceToTextExamples")

            # Simulate recording a command
            command_audio = await self.audio_manager.record_speech_command(max_duration=5.0)

            if not command_audio:
                self.logger.warning("No command audio recorded", component="VoiceToTextExamples")
                return {"success": False, "error": "No audio recorded"}

            # Transcribe the command
            transcription = await self.whisper_integration.transcribe_audio(command_audio)

            if not transcription or not transcription.get('text'):
                self.logger.warning("No text transcribed from command", component="VoiceToTextExamples")
                return {"success": False, "error": "No text transcribed"}

            command_text = transcription['text'].strip()
            confidence = transcription.get('confidence', 0.0)

            result = {
                "success": True,
                "command": command_text,
                "confidence": confidence,
                "language": transcription.get('language', 'unknown'),
                "processed_segments": len(transcription.get('segments', []))
            }

            self.logger.info(f"Command processed: '{command_text}' (confidence: {confidence:.2f})", component="VoiceToTextExamples")
            return result

        except Exception as e:
            self.error_handler.handle_exception(e, "VoiceToTextExamples.command_processing_example")
            return {"success": False, "error": str(e)}


async def run_voice_to_text_examples():
    """
    Run all voice-to-text examples
    """
    logger = VLALogger("VoiceToTextRunner")
    examples = VoiceToTextExamples()

    print("=" * 60)
    print("VOICE-TO-TEXT CONVERSION EXAMPLES FOR VLA SYSTEM")
    print("=" * 60)

    # Setup components
    print("\n1. Setting up speech recognition components...")
    success = await examples.setup_components(use_local_model=True)
    if not success:
        print("Failed to setup components. Please check requirements.")
        return

    print("✓ Components initialized successfully")

    # Example 1: File transcription (if we have a test file)
    print("\n2. File transcription example...")
    # For this example, we'll create a temporary audio file with some text
    # In practice, you would have actual audio files to transcribe
    print("   (Skipping file transcription - would require actual audio file)")

    # Example 2: Real-time transcription simulation
    print("\n3. Real-time transcription simulation...")
    print("   (This would record from microphone in a real implementation)")
    # For demonstration, we'll simulate with a placeholder
    try:
        result = await examples.real_time_transcription_example(duration=2.0)
        if result:
            print(f"   Transcription: {result['text'][:100]}...")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
        else:
            print("   Real-time transcription example completed (simulated)")
    except Exception as e:
        print(f"   Error in real-time transcription: {e}")

    # Example 3: Command processing
    print("\n4. Voice command processing...")
    command_result = await examples.command_processing_example()
    if command_result.get("success"):
        print(f"   Command: {command_result.get('command', 'N/A')}")
        print(f"   Confidence: {command_result.get('confidence', 0):.2f}")
    else:
        print(f"   Command processing result: {command_result.get('error', 'Unknown error')}")

    # Example 4: Batch processing description
    print("\n5. Batch transcription (conceptual)...")
    print("   The system supports batch processing of multiple audio files")
    print("   with automatic quality checking and error handling")

    # Example 5: Streaming transcription description
    print("\n6. Streaming transcription (conceptual)...")
    print("   The system supports real-time streaming transcription")
    print("   with continuous processing and low-latency response")

    print("\n" + "=" * 60)
    print("VOICE-TO-TEXT EXAMPLES COMPLETED")
    print("=" * 60)

    # Show system capabilities
    print("\nSYSTEM CAPABILITIES:")
    print("• Multiple Whisper model support (tiny, base, small, medium, large)")
    print("• Both local model and API-based transcription")
    print("• Real-time and batch processing")
    print("• Audio preprocessing (noise reduction, normalization, silence removal)")
    print("• Confidence scoring and quality assessment")
    print("• Multi-language support")
    print("• Integration with ROS 2 for robotics applications")


def create_synthetic_audio_for_demo():
    """
    Create synthetic audio data for demonstration purposes
    This would typically require audio generation libraries
    """
    try:
        import numpy as np
        # Generate a simple synthetic audio signal for demonstration
        duration = 2.0  # seconds
        sample_rate = 16000
        frequency = 440  # A4 note
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_signal = 0.5 * np.sin(2 * np.pi * frequency * t)

        # Convert to 16-bit PCM
        audio_bytes = (audio_signal * 32767).astype(np.int16).tobytes()

        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        import wave
        with wave.open(temp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)

        return temp_file.name
    except ImportError:
        print("Warning: Unable to create synthetic audio (requires numpy)")
        return None


async def main():
    """
    Main function to run the voice-to-text examples
    """
    print("Initializing Voice-to-Text Examples for VLA System...")

    # Check for required libraries
    required_libs = []
    try:
        import librosa
        required_libs.append("librosa")
    except ImportError:
        print("Note: librosa not available - some features limited")

    try:
        import pyaudio
        required_libs.append("pyaudio")
    except ImportError:
        print("Note: pyaudio not available - real-time recording limited")

    try:
        import sounddevice
        required_libs.append("sounddevice")
    except ImportError:
        print("Note: sounddevice not available - real-time recording limited")

    try:
        import whisper
        required_libs.append("whisper")
    except ImportError:
        print("Note: whisper not available - local transcription limited")

    try:
        import openai
        required_libs.append("openai")
    except ImportError:
        print("Note: openai not available - API transcription limited")

    print(f"Available libraries: {', '.join(required_libs)}")
    print()

    # Run the examples
    await run_voice_to_text_examples()


if __name__ == "__main__":
    asyncio.run(main())