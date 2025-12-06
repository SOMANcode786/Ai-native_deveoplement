"""
Base VLA Loop Structure: Vision-Language-Action Framework

This module implements the core VLA loop that connects input processing,
LLM planning, robot action execution, and visual feedback.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from .llm_integration import LLMManager, LLMConfig, LLMProvider, ActionStep
from .speech_recognition import SpeechRecognitionManager, SpeechRecognitionConfig, SpeechRecognitionProvider, SpeechResult
from .error_handling import ErrorHandler, VLALogger, VLAErrorType, handle_vla_error
from .vla_config import get_vla_config


class VLAState(Enum):
    """Current state of the VLA system"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    PLANNING = "planning"
    EXECUTING = "executing"
    FEEDBACK = "feedback"
    ERROR = "error"


@dataclass
class VLALoopConfig:
    """Configuration for the VLA loop"""
    enable_speech: bool = True
    enable_vision: bool = True
    enable_llm: bool = True
    max_command_history: int = 10
    response_timeout: int = 30
    feedback_timeout: int = 10


class VLALoop:
    """Main VLA loop that orchestrates the Input → LLM Plan → Robot Action → Visual Feedback cycle"""

    def __init__(self, config: Optional[VLALoopConfig] = None):
        self.config = config or VLALoopConfig()
        self.state = VLAState.IDLE
        self.logger = VLALogger("VLALoop")
        self.error_handler = ErrorHandler(self.logger)

        # Initialize components based on configuration
        self.llm_manager = None
        self.speech_manager = None

        if self.config.enable_llm:
            vla_config = get_vla_config()
            llm_config = LLMConfig(
                provider=LLMProvider(vla_config.llm_provider),
                api_key=vla_config.llm_api_key,
                model=vla_config.llm_model,
                temperature=vla_config.llm_temperature,
                max_tokens=vla_config.llm_max_tokens,
                timeout=vla_config.llm_timeout
            )
            try:
                self.llm_manager = LLMManager(llm_config)
                self.logger.info("LLM Manager initialized", component="VLALoop")
            except Exception as e:
                handle_vla_error(
                    VLAErrorType.CONFIGURATION_ERROR,
                    f"Failed to initialize LLM Manager: {e}",
                    "VLALoop"
                )

        if self.config.enable_speech:
            vla_config = get_vla_config()
            speech_config = SpeechRecognitionConfig(
                provider=SpeechRecognitionProvider(vla_config.speech_provider),
                api_key=vla_config.speech_api_key,
                model=vla_config.speech_model,
                language=vla_config.speech_language,
                sample_rate=vla_config.speech_sample_rate
            )
            try:
                self.speech_manager = SpeechRecognitionManager(speech_config)
                self.logger.info("Speech Manager initialized", component="VLALoop")
            except Exception as e:
                handle_vla_error(
                    VLAErrorType.CONFIGURATION_ERROR,
                    f"Failed to initialize Speech Manager: {e}",
                    "VLALoop"
                )

        # Command history for context
        self.command_history: List[Dict[str, Any]] = []
        self.action_history: List[Dict[str, Any]] = []

    async def run_loop(self):
        """Main VLA loop - runs continuously until stopped"""
        self.logger.info("Starting VLA loop", component="VLALoop")
        self.state = VLAState.IDLE

        while True:
            try:
                # 1. INPUT: Get user command (voice or text)
                self.state = VLAState.LISTENING
                command = await self.get_user_input()

                if command is None:
                    # No command received, continue loop
                    continue

                # 2. LLM PLAN: Generate action sequence from command
                self.state = VLAState.PLANNING
                action_sequence = await self.plan_actions(command)

                if not action_sequence:
                    self.logger.warning("No action sequence generated", component="VLALoop")
                    continue

                # 3. ROBOT ACTION: Execute the action sequence
                self.state = VLAState.EXECUTING
                execution_result = await self.execute_actions(action_sequence)

                # 4. VISUAL FEEDBACK: Get feedback from environment
                self.state = VLAState.FEEDBACK
                feedback = await self.get_visual_feedback(execution_result)

                # Process feedback and update history
                self._update_histories(command, action_sequence, execution_result, feedback)

                self.logger.info(f"VLA cycle completed. State: {feedback.get('status', 'unknown')}",
                               component="VLALoop")

            except KeyboardInterrupt:
                self.logger.info("VLA loop interrupted by user", component="VLALoop")
                break
            except Exception as e:
                self.state = VLAState.ERROR
                self.error_handler.handle_exception(e, "VLALoop")

                # Add error recovery - return to idle after error
                self.state = VLAState.IDLE
                await asyncio.sleep(1)  # Brief pause before continuing

    async def get_user_input(self) -> Optional[str]:
        """Get user input (voice or text)"""
        try:
            if self.config.enable_speech and self.speech_manager:
                # For now, simulate speech recognition
                # In a real implementation, this would capture audio from microphone
                self.logger.info("Listening for voice command...", component="VLALoop")

                # Simulate getting a command (in real implementation, this would be actual speech recognition)
                # For demo purposes, we'll return a placeholder command
                return "Move the red block to the blue area"
            else:
                # For now, return a placeholder command
                return "Pick up the object and place it on the table"
        except Exception as e:
            self.error_handler.handle_exception(e, "VLALoop.get_user_input")
            return None

    async def plan_actions(self, command: str) -> List[ActionStep]:
        """Use LLM to plan actions based on the command"""
        try:
            if not self.llm_manager:
                self.logger.error("LLM Manager not available", component="VLALoop")
                return []

            # Get context from history for better planning
            context = self._build_context()

            # Plan the action sequence
            action_sequence = await self.llm_manager.plan_action_sequence(command, context)

            # Validate the plan
            is_valid = await self.llm_manager.validate_plan(action_sequence)
            if not is_valid:
                self.logger.warning("Generated action sequence is not valid", component="VLALoop")
                return []

            self.logger.info(f"Planned {len(action_sequence)} actions", component="VLALoop")
            return action_sequence
        except Exception as e:
            self.error_handler.handle_exception(e, "VLALoop.plan_actions")
            return []

    async def execute_actions(self, action_sequence: List[ActionStep]) -> Dict[str, Any]:
        """Execute the planned action sequence"""
        try:
            results = []

            for i, action in enumerate(action_sequence):
                self.logger.info(f"Executing action {i+1}/{len(action_sequence)}: {action.description}",
                               component="VLALoop")

                # In a real implementation, this would interface with ROS 2
                # For now, we'll simulate execution
                result = await self._execute_single_action(action)
                results.append(result)

                # Check if action was successful
                if not result.get('success', True):
                    self.logger.error(f"Action failed: {action.description}", component="VLALoop")
                    break

            return {
                'success': len(results) == len(action_sequence),
                'executed_actions': results,
                'total_actions': len(action_sequence)
            }
        except Exception as e:
            self.error_handler.handle_exception(e, "VLALoop.execute_actions")
            return {'success': False, 'error': str(e)}

    async def _execute_single_action(self, action: ActionStep) -> Dict[str, Any]:
        """Execute a single action (placeholder implementation)"""
        try:
            # This is where ROS 2 integration would happen in a real implementation
            # For now, simulate different types of actions

            # Simulate action execution time
            await asyncio.sleep(0.5)

            # Return success result
            return {
                'action_type': action.action_type,
                'parameters': action.parameters,
                'description': action.description,
                'success': True,
                'timestamp': asyncio.get_event_loop().time()
            }
        except Exception as e:
            return {
                'action_type': action.action_type,
                'parameters': action.parameters,
                'description': action.description,
                'success': False,
                'error': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }

    async def get_visual_feedback(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """Get visual feedback after action execution"""
        try:
            # In a real implementation, this would interface with computer vision
            # For now, simulate feedback

            success = execution_result.get('success', False)

            feedback = {
                'status': 'success' if success else 'partial_success',
                'execution_result': execution_result,
                'timestamp': asyncio.get_event_loop().time(),
                'environment_state': 'normal'  # Would come from vision system
            }

            self.logger.info(f"Visual feedback: {feedback['status']}", component="VLALoop")
            return feedback
        except Exception as e:
            self.error_handler.handle_exception(e, "VLALoop.get_visual_feedback")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }

    def _build_context(self) -> str:
        """Build context from command and action history"""
        context_parts = []

        # Add recent commands
        if self.command_history:
            recent_commands = self.command_history[-3:]  # Last 3 commands
            context_parts.append("Recent commands:")
            for cmd in recent_commands:
                context_parts.append(f"- {cmd['command']} -> {cmd['result']}")

        # Add recent actions
        if self.action_history:
            recent_actions = self.action_history[-3:]  # Last 3 action sets
            context_parts.append("Recent actions:")
            for action_set in recent_actions:
                context_parts.append(f"- {len(action_set['actions'])} actions executed: {action_set['status']}")

        return "\n".join(context_parts)

    def _update_histories(self, command: str, action_sequence: List[ActionStep],
                         execution_result: Dict[str, Any], feedback: Dict[str, Any]):
        """Update command and action histories"""
        # Update command history
        self.command_history.append({
            'command': command,
            'action_count': len(action_sequence),
            'result': execution_result.get('success', False),
            'timestamp': asyncio.get_event_loop().time()
        })

        # Keep history within limits
        if len(self.command_history) > self.config.max_command_history:
            self.command_history = self.command_history[-self.config.max_command_history:]

        # Update action history
        self.action_history.append({
            'actions': [action.description for action in action_sequence],
            'execution_result': execution_result,
            'feedback': feedback,
            'timestamp': asyncio.get_event_loop().time()
        })

        # Keep history within limits
        if len(self.action_history) > self.config.max_command_history:
            self.action_history = self.action_history[-self.config.max_command_history:]

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the VLA loop"""
        return {
            'state': self.state.value,
            'command_history_length': len(self.command_history),
            'action_history_length': len(self.action_history),
            'error_count': self.error_handler.get_error_count()
        }

    async def stop(self):
        """Stop the VLA loop"""
        self.logger.info("Stopping VLA loop", component="VLALoop")
        # In a real implementation, this would clean up resources


# Example usage
async def main():
    """Example of how to use the VLA loop"""
    # Initialize configuration
    from .vla_config import init_config
    init_config()

    # Create VLA loop
    vla_loop = VLALoop()

    # Start the loop (this will run indefinitely until interrupted)
    try:
        await vla_loop.run_loop()
    except KeyboardInterrupt:
        print("\nVLA loop stopped by user")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())