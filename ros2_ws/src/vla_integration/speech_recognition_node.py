#!/usr/bin/env python3
"""
ROS 2 Node for Speech Recognition in Vision-Language-Action (VLA) System

This node integrates speech recognition capabilities with ROS 2,
converting audio input to text commands for the VLA system.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import String, Bool
from sensor_msgs.msg import AudioData
from vla_interfaces.action import VLACommand  # Custom action
from vla_interfaces.srv import VLAPrompt  # Custom service

import asyncio
import threading
import logging
from typing import Optional, Dict, Any
from pathlib import Path

# Import our speech recognition modules
from src.speech_recognition.whisper_integration import WhisperIntegration
from src.speech_recognition.audio_input import AudioInputManager, AudioConfig
from src.error_handling import ErrorHandler, VLALogger, VLAException, VLAErrorType


class SpeechRecognitionNode(Node):
    """
    ROS 2 Node that handles speech recognition functionality
    Subscribes to audio data, processes it through Whisper, and publishes text commands
    """

    def __init__(self):
        super().__init__('speech_recognition_node')

        # Initialize logging
        self.logger = VLALogger('SpeechRecognitionNode')
        self.error_handler = ErrorHandler(self.logger)

        # Node parameters
        self.declare_parameter('whisper_model', 'base')
        self.declare_parameter('use_local_model', True)
        self.declare_parameter('api_key', '')
        self.declare_parameter('sample_rate', 16000)
        self.declare_parameter('language', 'en')

        # Get parameters
        whisper_model = self.get_parameter('whisper_model').get_parameter_value().string_value
        use_local_model = self.get_parameter('use_local_model').get_parameter_value().bool_value
        api_key = self.get_parameter('api_key').get_parameter_value().string_value
        sample_rate = self.get_parameter('sample_rate').get_parameter_value().integer_value
        language = self.get_parameter('language').get_parameter_value().string_value

        # Initialize speech recognition components
        try:
            self.whisper_integration = WhisperIntegration(
                api_key=api_key if not use_local_model else None,
                model_name=whisper_model,
                use_local=use_local_model
            )

            audio_config = AudioConfig(sample_rate=sample_rate)
            self.audio_manager = AudioInputManager(audio_config)

            self.language = language
            self.is_listening = False
            self.recording_thread = None

            self.logger.info("Speech recognition components initialized", component="SpeechRecognitionNode")
        except Exception as e:
            self.error_handler.handle_exception(e, "SpeechRecognitionNode.__init__")
            raise

        # Create publishers
        self.text_command_pub = self.create_publisher(
            String,
            'vla/text_command',
            QoSProfile(depth=10)
        )

        self.status_pub = self.create_publisher(
            String,
            'vla/speech_status',
            QoSProfile(depth=10)
        )

        # Create subscribers
        self.audio_sub = self.create_subscription(
            AudioData,
            'audio/audio_data',
            self.audio_callback,
            QoSProfile(depth=10)
        )

        # Create services
        self.transcribe_srv = self.create_service(
            VLAPrompt,  # Using our custom service for transcription requests
            'vla/transcribe_audio',
            self.transcribe_audio_callback
        )

        # Create timers
        self.status_timer = self.create_timer(1.0, self.publish_status)

        self.logger.info("Speech recognition node initialized", component="SpeechRecognitionNode")

    def audio_callback(self, msg: AudioData):
        """
        Callback for audio data messages
        Processes audio and converts to text command
        """
        try:
            self.logger.info("Received audio data", component="SpeechRecognitionNode")

            # Convert AudioData message to bytes
            audio_bytes = bytes(msg.data)

            # Process audio through Whisper asynchronously
            # Since ROS 2 callbacks are synchronous, we'll use a thread
            future = asyncio.run_coroutine_threadsafe(
                self.process_audio_async(audio_bytes),
                self.get_async_loop()
            )

        except Exception as e:
            self.error_handler.handle_exception(e, "SpeechRecognitionNode.audio_callback")

    async def process_audio_async(self, audio_data: bytes) -> Optional[str]:
        """
        Process audio data asynchronously through Whisper
        """
        try:
            self.logger.info(f"Processing {len(audio_data)} bytes of audio", component="SpeechRecognitionNode")

            # Transcribe the audio
            result = await self.whisper_integration.transcribe_audio(
                audio_data,
                language=self.language
            )

            if result and result.get('text'):
                text_command = result['text'].strip()
                confidence = result.get('confidence', 0.0)

                if confidence > 0.5:  # Only publish if confidence is high enough
                    # Publish the text command
                    text_msg = String()
                    text_msg.data = text_command
                    self.text_command_pub.publish(text_msg)

                    self.logger.info(f"Published text command: {text_command[:50]}...", component="SpeechRecognitionNode")
                    return text_command
                else:
                    self.logger.warning(f"Low confidence transcription: {confidence}", component="SpeechRecognitionNode")
                    return None
            else:
                self.logger.warning("No text extracted from audio", component="SpeechRecognitionNode")
                return None

        except Exception as e:
            self.error_handler.handle_exception(e, "SpeechRecognitionNode.process_audio_async")
            return None

    def transcribe_audio_callback(self, request: VLAPrompt.Request, response: VLAPrompt.Response):
        """
        Service callback for manual audio transcription requests
        """
        try:
            self.logger.info("Received transcription request", component="SpeechRecognitionNode")

            # For now, we'll simulate the transcription
            # In a real implementation, this would process the audio data in the request
            response.success = True
            response.message = "Transcription service received request"
            response.action_sequence = [request.natural_language_command]  # Echo back as example

            self.logger.info(f"Processed transcription request: {request.natural_language_command}", component="SpeechRecognitionNode")
            return response

        except Exception as e:
            self.error_handler.handle_exception(e, "SpeechRecognitionNode.transcribe_audio_callback")
            response.success = False
            response.message = f"Error in transcription: {str(e)}"
            response.action_sequence = []
            return response

    def publish_status(self):
        """Publish node status"""
        status_msg = String()
        status_msg.data = f"Speech recognition node active - Listening: {self.is_listening}"
        self.status_pub.publish(status_msg)

    def start_listening(self):
        """Start continuous listening for audio input"""
        if self.is_listening:
            self.logger.warning("Already listening", component="SpeechRecognitionNode")
            return

        self.is_listening = True
        self.logger.info("Starting to listen for audio", component="SpeechRecognitionNode")

        # In a real implementation, this would start the microphone
        # For now, we'll just log that we're ready to receive audio

    def stop_listening(self):
        """Stop listening for audio input"""
        self.is_listening = False
        self.logger.info("Stopped listening for audio", component="SpeechRecognitionNode")

    def get_async_loop(self):
        """
        Get or create an asyncio event loop for this node
        """
        if not hasattr(self, '_async_loop'):
            self._async_loop = asyncio.new_event_loop()
            # Start the event loop in a separate thread
            self._loop_thread = threading.Thread(target=self._async_loop.run_forever, daemon=True)
            self._loop_thread.start()

        return self._async_loop


def main(args=None):
    """Main function to run the speech recognition node"""
    rclpy.init(args=args)

    try:
        node = SpeechRecognitionNode()
        node.logger.info("Starting speech recognition node", component="SpeechRecognitionNode")

        # Start listening
        node.start_listening()

        # Spin the node
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.logger.info("Interrupted by user", component="SpeechRecognitionNode")
    except Exception as e:
        if 'node' in locals():
            node.error_handler.handle_exception(e, "SpeechRecognitionNode.main")
    finally:
        if 'node' in locals():
            node.stop_listening()
            node.destroy_node()
        rclpy.shutdown()


# Additional ROS 2 utilities for speech recognition
class SpeechRecognitionUtils:
    """Utility functions for speech recognition in ROS 2 context"""

    @staticmethod
    def audio_data_to_wav(audio_msg: AudioData, sample_rate: int = 16000, channels: int = 1) -> bytes:
        """
        Convert ROS AudioData message to WAV format bytes
        """
        try:
            import io
            import wave

            # Create WAV file in memory
            wav_buffer = io.BytesIO()

            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(bytes(audio_msg.data))

            return wav_buffer.getvalue()

        except Exception as e:
            raise RuntimeError(f"Failed to convert AudioData to WAV: {e}")

    @staticmethod
    def validate_audio_message(audio_msg: AudioData) -> bool:
        """
        Validate that the audio message contains valid data
        """
        if not audio_msg or not audio_msg.data:
            return False

        # Check for minimum data length
        if len(audio_msg.data) < 100:  # Minimum 100 bytes for meaningful audio
            return False

        return True


if __name__ == '__main__':
    main()