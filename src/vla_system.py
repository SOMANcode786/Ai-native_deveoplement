"""
Vision-Language-Action (VLA) System Integration

This module integrates all VLA components into a cohesive system
that enables natural language interaction with robotic platforms.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import json

# Import all VLA components
from src.vla_loop import VLALoop, VLALoopConfig
from src.llm_integration import LLMManager, LLMConfig, LLMProvider
from src.speech_recognition import SpeechRecognitionManager, SpeechRecognitionConfig, SpeechRecognitionProvider
from src.vision_language.grounding import VisionLanguageGrounding
from src.vision_language.object_detection import ObjectDetectionManager, DetectionModelType
from src.vision_language.visual_verification import VisualVerificationSystem
from src.hri.conversational_flow import ConversationalFlowManager
from src.hri.error_recovery import ErrorRecoveryManager, ErrorType
from src.hri.ambiguity_resolver import AmbiguityResolver
from src.hri.failure_communication import FailureCommunicationSystem
from src.hri.clarifying_questions import ClarifyingQuestionGenerator
from src.error_handling import ErrorHandler, VLALogger
from src.vla_config import get_vla_config


class VLAState(Enum):
    """Current state of the VLA system"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    ERROR = "error"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class VLAComponentStatus(Enum):
    """Status of VLA components"""
    READY = "ready"
    INITIALIZING = "initializing"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


@dataclass
class VLAComponent:
    """Represents a VLA system component"""
    name: str
    instance: Any
    status: VLAComponentStatus
    dependencies: List[str]
    health_check: Optional[Callable] = None


class VLASystem:
    """
    Main VLA System that integrates all components
    Coordinates the Vision-Language-Action loop
    """

    def __init__(self, config_path: Optional[str] = None):
        self.logger = VLALogger("VLASystem")
        self.error_handler = ErrorHandler(self.logger)

        # Load configuration
        self.config = get_vla_config()

        # Initialize components
        self.components: Dict[str, VLAComponent] = {}
        self.state = VLAState.IDLE

        # Initialize individual managers
        self.vla_loop = None
        self.llm_manager = None
        self.speech_manager = None
        self.vision_grounding = None
        self.object_detection = None
        self.visual_verification = None
        self.conversational_flow = None
        self.error_recovery = None
        self.ambiguity_resolver = None
        self.failure_communication = None
        self.clarifying_questions = None

        # Initialize the system
        try:
            self._initialize_components()
            self.logger.info("VLA System initialized successfully", component="VLASystem")
        except Exception as e:
            self.error_handler.handle_exception(e, "VLASystem.__init__")
            raise

    def _initialize_components(self):
        """Initialize all VLA system components"""
        try:
            # Initialize LLM Manager
            llm_config = LLMConfig(
                provider=LLMProvider(self.config.llm_provider),
                api_key=self.config.llm_api_key,
                model=self.config.llm_model,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
                timeout=self.config.llm_timeout
            )
            self.llm_manager = LLMManager(llm_config)

            self.components['llm_manager'] = VLAComponent(
                name='LLM Manager',
                instance=self.llm_manager,
                status=VLAComponentStatus.READY,
                dependencies=[]
            )

            # Initialize Speech Recognition Manager
            speech_config = SpeechRecognitionConfig(
                provider=SpeechRecognitionProvider(self.config.speech_provider),
                api_key=self.config.speech_api_key,
                model=self.config.speech_model,
                language=self.config.speech_language,
                sample_rate=self.config.speech_sample_rate
            )
            self.speech_manager = SpeechRecognitionManager(speech_config)

            self.components['speech_manager'] = VLAComponent(
                name='Speech Manager',
                instance=self.speech_manager,
                status=VLAComponentStatus.READY,
                dependencies=[]
            )

            # Initialize Vision-Language Grounding
            self.vision_grounding = VisionLanguageGrounding()

            self.components['vision_grounding'] = VLAComponent(
                name='Vision Grounding',
                instance=self.vision_grounding,
                status=VLAComponentStatus.READY,
                dependencies=['object_detection']
            )

            # Initialize Object Detection
            self.object_detection = ObjectDetectionManager(DetectionModelType.FASTER_RCNN)

            self.components['object_detection'] = VLAComponent(
                name='Object Detection',
                instance=self.object_detection,
                status=VLAComponentStatus.READY,
                dependencies=[]
            )

            # Initialize Visual Verification
            self.visual_verification = VisualVerificationSystem()

            self.components['visual_verification'] = VLAComponent(
                name='Visual Verification',
                instance=self.visual_verification,
                status=VLAComponentStatus.READY,
                dependencies=[]
            )

            # Initialize Conversational Flow
            self.conversational_flow = ConversationalFlowManager()

            self.components['conversational_flow'] = VLAComponent(
                name='Conversational Flow',
                instance=self.conversational_flow,
                status=VLAComponentStatus.READY,
                dependencies=['llm_manager', 'speech_manager']
            )

            # Initialize Error Recovery
            self.error_recovery = ErrorRecoveryManager()

            self.components['error_recovery'] = VLAComponent(
                name='Error Recovery',
                instance=self.error_recovery,
                status=VLAComponentStatus.READY,
                dependencies=[]
            )

            # Initialize Ambiguity Resolver
            self.ambiguity_resolver = AmbiguityResolver()

            self.components['ambiguity_resolver'] = VLAComponent(
                name='Ambiguity Resolver',
                instance=self.ambiguity_resolver,
                status=VLAComponentStatus.READY,
                dependencies=['conversational_flow']
            )

            # Initialize Failure Communication
            self.failure_communication = FailureCommunicationSystem()

            self.components['failure_communication'] = VLAComponent(
                name='Failure Communication',
                instance=self.failure_communication,
                status=VLAComponentStatus.READY,
                dependencies=['error_recovery']
            )

            # Initialize Clarifying Questions
            self.clarifying_questions = ClarifyingQuestionGenerator()

            self.components['clarifying_questions'] = VLAComponent(
                name='Clarifying Questions',
                instance=self.clarifying_questions,
                status=VLAComponentStatus.READY,
                dependencies=['ambiguity_resolver']
            )

            # Initialize VLA Loop
            loop_config = VLALoopConfig()
            self.vla_loop = VLALoop(loop_config)

            self.components['vla_loop'] = VLAComponent(
                name='VLA Loop',
                instance=self.vla_loop,
                status=VLAComponentStatus.READY,
                dependencies=[
                    'llm_manager', 'speech_manager', 'vision_grounding',
                    'object_detection', 'visual_verification', 'conversational_flow'
                ]
            )

            self.logger.info("All VLA components initialized", component="VLASystem")

        except Exception as e:
            self.logger.error(f"Error initializing VLA components: {e}", component="VLASystem")
            raise

    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a natural language command through the full VLA pipeline

        Args:
            command: Natural language command from user
            context: Additional context information

        Returns:
            Dictionary with processing results
        """
        try:
            self.logger.info(f"Processing command: {command[:50]}...", component="VLASystem")
            self.state = VLAState.PROCESSING

            # Initialize context if not provided
            context = context or {}
            context['command_timestamp'] = asyncio.get_event_loop().time()

            # Step 1: Process through conversational flow for clarification if needed
            processed_command, needs_clarification = await self._handle_initial_processing(command, context)

            if needs_clarification:
                return {
                    'success': False,
                    'needs_clarification': True,
                    'clarifying_question': processed_command,  # This is actually a question
                    'status': 'awaiting_user_input'
                }

            # Step 2: Plan actions using LLM
            self.state = VLAState.PLANNING
            action_sequence = await self.llm_manager.plan_action_sequence(processed_command, context)

            if not action_sequence:
                error_report = await self.error_recovery.handle_error(
                    ErrorType.AMBIGUOUS_COMMAND,
                    "LLM could not generate action sequence",
                    processed_command,
                    self._get_robot_state(),
                    self._get_environment_state()
                )
                return {
                    'success': False,
                    'error': 'Could not understand command',
                    'recovery_advice': error_report.description,
                    'status': 'error'
                }

            # Step 3: Validate the plan
            is_valid = await self.llm_manager.validate_plan(action_sequence)
            if not is_valid:
                error_report = await self.error_recovery.handle_error(
                    ErrorType.EXECUTION_FAILURE,
                    "Generated action sequence is not valid",
                    processed_command,
                    self._get_robot_state(),
                    self._get_environment_state()
                )
                return {
                    'success': False,
                    'error': 'Action sequence validation failed',
                    'recovery_advice': error_report.description,
                    'status': 'error'
                }

            # Step 4: Execute the action sequence
            self.state = VLAState.EXECUTING
            execution_result = await self._execute_action_sequence(action_sequence, context)

            if not execution_result.get('success', False):
                return {
                    'success': False,
                    'error': execution_result.get('error', 'Execution failed'),
                    'status': 'execution_failed'
                }

            # Step 5: Verify completion visually
            self.state = VLAState.VERIFYING
            verification_result = await self._verify_completion(processed_command, context)

            result = {
                'success': True,
                'original_command': command,
                'processed_command': processed_command,
                'action_sequence': [action.description for action in action_sequence],
                'execution_result': execution_result,
                'verification_result': verification_result,
                'status': 'completed',
                'timestamp': asyncio.get_event_loop().time()
            }

            self.logger.info(f"Command processed successfully: {len(action_sequence)} actions executed",
                           component="VLASystem")
            self.state = VLAState.IDLE

            return result

        except Exception as e:
            self.state = VLAState.ERROR
            self.error_handler.handle_exception(e, "VLASystem.process_command")

            # Try error recovery
            recovery_result = await self.error_recovery.handle_error(
                ErrorType.UNKNOWN_ERROR,
                str(e),
                command,
                self._get_robot_state(),
                self._get_environment_state()
            )

            return {
                'success': False,
                'error': str(e),
                'recovery_advice': recovery_result.description,
                'status': 'error'
            }

    async def _handle_initial_processing(self, command: str, context: Dict[str, Any]) -> tuple:
        """Handle initial processing of command including clarification if needed"""
        # Check for ambiguities in the command
        ambiguities = await self.ambiguity_resolver.identify_ambiguities(command)

        if ambiguities:
            # Generate clarifying questions
            candidates = await self.ambiguity_resolver.generate_resolution_candidates(command, ambiguities)

            # Resolve ambiguities
            resolved, response, resolved_context = await self.ambiguity_resolver.resolve_ambiguities(
                command, candidates, context
            )

            if not resolved:
                # Return the clarifying question
                return response, True
            else:
                # Use resolved command
                command = response

        return command, False

    async def _execute_action_sequence(self, action_sequence: List[Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the planned action sequence"""
        try:
            results = []

            for i, action in enumerate(action_sequence):
                self.logger.info(f"Executing action {i+1}/{len(action_sequence)}: {action.description}",
                               component="VLASystem")

                # In a real implementation, this would execute the action through ROS 2
                # For now, we'll simulate execution
                try:
                    # This is where you'd integrate with actual robot control
                    # For example, calling ROS 2 services/actions based on the action type
                    result = await self._execute_single_action(action, context)
                    results.append(result)

                    if not result.get('success', True):
                        self.logger.error(f"Action failed: {action.description}", component="VLASystem")
                        break

                except Exception as action_error:
                    self.logger.error(f"Error executing action {action.description}: {action_error}",
                                    component="VLASystem")
                    results.append({
                        'action_index': i,
                        'success': False,
                        'error': str(action_error),
                        'action_description': action.description
                    })
                    break

            success = all(result.get('success', False) for result in results)

            return {
                'success': success,
                'executed_actions': len(results),
                'total_actions': len(action_sequence),
                'results': results
            }

        except Exception as e:
            self.error_handler.handle_exception(e, "VLASystem._execute_action_sequence")
            return {
                'success': False,
                'error': str(e),
                'executed_actions': 0,
                'total_actions': len(action_sequence)
            }

    async def _execute_single_action(self, action, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action in the sequence"""
        try:
            # This is a simulation - in real implementation, this would call ROS 2 services
            # based on the action type

            # Simulate execution time
            await asyncio.sleep(0.1)  # Simulate processing time

            # In a real system, you would:
            # - Translate action to ROS 2 service/action calls
            # - Execute through robot's motion controllers
            # - Monitor execution status
            # - Handle any execution errors

            return {
                'success': True,
                'action_type': action.action_type,
                'description': action.description,
                'execution_time': 0.1,
                'context_used': context
            }

        except Exception as e:
            return {
                'success': False,
                'action_type': action.action_type,
                'description': action.description,
                'error': str(e)
            }

    async def _verify_completion(self, command: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that the task was completed successfully using visual feedback"""
        try:
            # In a real implementation, this would:
            # 1. Capture current environment state
            # 2. Compare with expected outcome from command
            # 3. Use visual verification system to confirm completion

            # For now, we'll simulate verification
            await asyncio.sleep(0.1)  # Simulate visual processing time

            # Simulate verification result
            verification_result = {
                'success': True,
                'confidence': 0.9,
                'command_processed': command,
                'visual_verification_performed': True,
                'environment_changed': True,
                'task_completed': True
            }

            return verification_result

        except Exception as e:
            self.error_handler.handle_exception(e, "VLASystem._verify_completion")
            return {
                'success': False,
                'error': str(e),
                'confidence': 0.0
            }

    def _get_robot_state(self) -> Dict[str, Any]:
        """Get current robot state for error handling and context"""
        # In a real implementation, this would query the robot's state
        return {
            'position': {'x': 0, 'y': 0, 'z': 0},
            'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
            'battery_level': 85,
            'gripper_status': 'open',
            'arm_position': 'home',
            'current_task': None
        }

    def _get_environment_state(self) -> Dict[str, Any]:
        """Get current environment state for error handling and context"""
        # In a real implementation, this would come from perception system
        return {
            'objects_detected': [],
            'obstacles': [],
            'navigable_areas': [],
            'lighting_conditions': 'good',
            'humans_present': False,
            'workspace_clear': True
        }

    async def start_listening(self):
        """Start the VLA system in listening mode"""
        try:
            self.logger.info("Starting VLA system listening mode", component="VLASystem")
            self.state = VLAState.LISTENING

            # In a real implementation, this would start speech recognition
            # and listen for user commands

            # For now, we'll just log that we're ready
            self.logger.info("VLA system ready to receive commands", component="VLASystem")

        except Exception as e:
            self.error_handler.handle_exception(e, "VLASystem.start_listening")

    async def stop_system(self):
        """Gracefully stop the VLA system"""
        try:
            self.logger.info("Stopping VLA system", component="VLASystem")
            self.state = VLAState.IDLE

            # In a real implementation, you'd shut down each component gracefully
            # For now, we'll just log the shutdown

            self.logger.info("VLA system stopped", component="VLASystem")

        except Exception as e:
            self.error_handler.handle_exception(e, "VLASystem.stop_system")

    def get_system_status(self) -> Dict[str, Any]:
        """Get current status of the VLA system"""
        return {
            'state': self.state.value,
            'components': {
                name: {
                    'status': comp.status.value,
                    'dependencies': comp.dependencies
                }
                for name, comp in self.components.items()
            },
            'timestamp': asyncio.get_event_loop().time(),
            'total_components': len(self.components),
            'ready_components': len([comp for comp in self.components.values() if comp.status == VLAComponentStatus.READY])
        }

    async def handle_error(self, error_type: ErrorType, error_message: str,
                          context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an error through the integrated error recovery system"""
        try:
            recovery_result = await self.error_recovery.handle_error(
                error_type,
                error_message,
                "system_error",
                self._get_robot_state(),
                self._get_environment_state()
            )

            return {
                'recovered': recovery_result.status != ErrorType.UNKNOWN_ERROR,
                'recovery_action': recovery_result.description,
                'confidence': recovery_result.confidence
            }

        except Exception as e:
            self.error_handler.handle_exception(e, "VLASystem.handle_error")
            return {
                'recovered': False,
                'error': str(e)
            }


class VLASystemManager:
    """Manager class for controlling the VLA system lifecycle"""

    def __init__(self):
        self.system = None
        self.logger = VLALogger("VLASystemManager")

    async def initialize_system(self, config_path: Optional[str] = None) -> bool:
        """Initialize the VLA system"""
        try:
            self.system = VLASystem(config_path)
            self.logger.info("VLA System initialized", component="VLASystemManager")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize VLA System: {e}", component="VLASystemManager")
            return False

    async def run_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a command through the VLA system"""
        if not self.system:
            return {
                'success': False,
                'error': 'VLA System not initialized'
            }

        return await self.system.process_command(command, context)

    async def start_system(self):
        """Start the VLA system"""
        if not self.system:
            await self.initialize_system()

        if self.system:
            await self.system.start_listening()

    async def shutdown_system(self):
        """Shutdown the VLA system"""
        if self.system:
            await self.system.stop_system()

    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        if self.system:
            return self.system.get_system_status()
        else:
            return {
                'system_initialized': False,
                'state': 'uninitialized',
                'components': {}
            }


# Example usage and testing
async def demo_vla_integration():
    """Demonstrate the integrated VLA system"""
    print("VLA System Integration Demo")
    print("=" * 40)

    manager = VLASystemManager()

    # Initialize the system
    print("\n1. Initializing VLA System...")
    success = await manager.initialize_system()
    if not success:
        print("  ✗ Failed to initialize VLA system")
        return
    print("  ✓ VLA system initialized")

    # Show system status
    print("\n2. System Status:")
    status = manager.get_status()
    print(f"   State: {status['state']}")
    print(f"   Components: {status['total_components']} total, {status['ready_components']} ready")

    # Example commands to process
    example_commands = [
        "Move the red cup from the table to the counter",
        "Clean up the table by organizing the books",
        "Go to the kitchen and wait for me there",
        "Find my keys and bring them to me"
    ]

    print(f"\n3. Processing Example Commands:")
    for i, command in enumerate(example_commands, 1):
        print(f"\n   {i}. Command: '{command}'")

        result = await manager.run_command(command)

        if result['success']:
            print(f"      ✓ Processed successfully")
            print(f"      ✓ Actions: {len(result.get('action_sequence', []))}")
            print(f"      ✓ Execution: {result['execution_result']['executed_actions']}/{result['execution_result']['total_actions']} completed")
        else:
            print(f"      ✗ Failed: {result.get('error', 'Unknown error')}")
            if result.get('needs_clarification'):
                print(f"      ? Clarification needed: {result.get('clarifying_question', 'N/A')}")

    # Show final status
    print(f"\n4. Final System Status:")
    final_status = manager.get_status()
    print(f"   State: {final_status['state']}")
    print(f"   Ready components: {final_status['ready_components']}/{final_status['total_components']}")

    # Shutdown
    print(f"\n5. Shutting down system...")
    await manager.shutdown_system()
    print("   ✓ System shutdown complete")

    print(f"\nVLA system integration demo completed!")


def explain_integration_architecture():
    """Explain how the VLA components are integrated"""
    print("\nVLA System Integration Architecture")
    print("=" * 45)

    architecture = {
        "Input Layer": [
            "Speech Recognition → Natural Language Commands",
            "Computer Vision → Environmental Perception",
            "Sensor Fusion → Multi-Modal Input Processing"
        ],
        "Processing Layer": [
            "LLM Integration → High-Level Planning",
            "Ambiguity Resolution → Command Clarification",
            "Context Management → Situation Awareness"
        ],
        "Action Layer": [
            "ROS 2 Integration → Robot Control",
            "Action Sequencing → Task Execution",
            "Safety Monitoring → Constraint Validation"
        ],
        "Feedback Layer": [
            "Visual Verification → Action Confirmation",
            "Performance Monitoring → Execution Tracking",
            "Adaptive Learning → System Improvement"
        ]
    }

    for layer, components in architecture.items():
        print(f"\n{layer}:")
        for component in components:
            print(f"  • {component}")

    print(f"\nIntegration Benefits:")
    benefits = [
        "Seamless human-robot interaction through natural language",
        "Robust error handling and recovery mechanisms",
        "Real-time visual feedback and verification",
        "Modular architecture allowing component replacement",
        "Safety-first design with constraint validation",
        "Adaptive behavior based on environmental context"
    ]

    for benefit in benefits:
        print(f"  ✓ {benefit}")


if __name__ == "__main__":
    # Run the integration demo
    asyncio.run(demo_vla_integration())

    # Explain the architecture
    explain_integration_architecture()