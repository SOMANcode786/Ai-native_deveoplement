"""
ROS 2 Action Sequence Generator for Vision-Language-Action (VLA) System

This module generates executable ROS 2 action sequences from high-level
LLM-generated plans for the VLA system.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import re

# Import ROS 2 related modules (with graceful degradation)
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from rclpy.callback_groups import ReentrantCallbackGroup
    from geometry_msgs.msg import Pose, Point, Quaternion
    from std_msgs.msg import String
    from sensor_msgs.msg import JointState
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    # Define minimal mock classes for testing
    class MockNode:
        def get_logger(self):
            return MockLogger()
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def warn(self, msg): print(f"WARN: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
    Node = MockNode

from src.llm_integration import ActionStep
from src.error_handling import ErrorHandler, VLALogger, VLAException, VLAErrorType


class ROS2ActionType(Enum):
    """Types of ROS 2 actions that can be generated"""
    NAVIGATION = "navigation"
    MANIPULATION = "manipulation"
    PERCEPTION = "perception"
    COMMUNICATION = "communication"
    MOBILITY = "mobility"
    GRASPING = "grasping"


@dataclass
class ROS2Action:
    """Represents a single ROS 2 action"""
    action_type: ROS2ActionType
    service_or_action_name: str
    parameters: Dict[str, Any]
    timeout: float = 30.0
    retry_count: int = 3
    description: str = ""


@dataclass
class ActionSequence:
    """Represents a complete sequence of ROS 2 actions"""
    actions: List[ROS2Action]
    original_command: str
    context: Dict[str, Any]
    generated_at: str


class ActionSequenceGenerator:
    """
    Generates ROS 2 action sequences from LLM-generated action steps
    """

    def __init__(self):
        self.logger = VLALogger("ActionSequenceGenerator")
        self.error_handler = ErrorHandler(self.logger)
        self.ros_node = None
        self.action_mapping = self._initialize_action_mapping()

    def _initialize_action_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Initialize mapping from natural action types to ROS 2 actions"""
        return {
            # Navigation actions
            "navigate": {
                "action_type": ROS2ActionType.NAVIGATION,
                "service": "/navigate_to_pose",
                "parameter_mapping": {
                    "target_location": "pose",
                    "x": "pose.position.x",
                    "y": "pose.position.y",
                    "z": "pose.position.z",
                    "orientation": "pose.orientation"
                }
            },
            "move_to": {
                "action_type": ROS2ActionType.NAVIGATION,
                "service": "/navigate_to_pose",
                "parameter_mapping": {
                    "target_location": "pose",
                    "x": "pose.position.x",
                    "y": "pose.position.y",
                    "z": "pose.position.z"
                }
            },
            "go_to": {
                "action_type": ROS2ActionType.NAVIGATION,
                "service": "/navigate_to_pose",
                "parameter_mapping": {
                    "location": "pose",
                    "x": "pose.position.x",
                    "y": "pose.position.y",
                    "z": "pose.position.z"
                }
            },
            # Manipulation actions
            "grasp": {
                "action_type": ROS2ActionType.GRASPING,
                "service": "/gripper_command",
                "parameter_mapping": {
                    "object_id": "object_id",
                    "grasp_type": "command",
                    "force": "force"
                }
            },
            "pick_up": {
                "action_type": ROS2ActionType.MANIPULATION,
                "service": "/pick_place",
                "parameter_mapping": {
                    "object": "target_object",
                    "pose": "target_pose"
                }
            },
            "place": {
                "action_type": ROS2ActionType.MANIPULATION,
                "service": "/pick_place",
                "parameter_mapping": {
                    "object": "target_object",
                    "destination": "target_pose"
                }
            },
            "move_object": {
                "action_type": ROS2ActionType.MANIPULATION,
                "service": "/move_object",
                "parameter_mapping": {
                    "object": "object_id",
                    "destination": "target_pose"
                }
            },
            # Perception actions
            "detect_object": {
                "action_type": ROS2ActionType.PERCEPTION,
                "service": "/object_detection",
                "parameter_mapping": {
                    "object_type": "target_class",
                    "color": "target_color",
                    "location": "search_area"
                }
            },
            "identify": {
                "action_type": ROS2ActionType.PERCEPTION,
                "service": "/object_detection",
                "parameter_mapping": {
                    "object_type": "target_class",
                    "location": "search_area"
                }
            },
            # Mobility actions
            "move_arm": {
                "action_type": ROS2ActionType.MOBILITY,
                "service": "/arm_controller/plan_and_execute",
                "parameter_mapping": {
                    "joint_positions": "joint_trajectory",
                    "pose": "target_pose"
                }
            },
            "rotate": {
                "action_type": ROS2ActionType.MOBILITY,
                "service": "/rotate_robot",
                "parameter_mapping": {
                    "angle": "target_angle",
                    "direction": "rotation_direction"
                }
            },
            # Communication actions
            "speak": {
                "action_type": ROS2ActionType.COMMUNICATION,
                "service": "/tts_service",
                "parameter_mapping": {
                    "text": "text_to_speak",
                    "language": "language"
                }
            },
            "say": {
                "action_type": ROS2ActionType.COMMUNICATION,
                "service": "/tts_service",
                "parameter_mapping": {
                    "text": "text_to_speak"
                }
            }
        }

    def generate_action_sequence(self, action_steps: List[ActionStep],
                               original_command: str,
                               context: Optional[Dict[str, Any]] = None) -> ActionSequence:
        """
        Generate a ROS 2 action sequence from LLM-generated action steps
        """
        try:
            ros_actions = []
            context = context or {}

            for step in action_steps:
                ros_action = self._convert_action_step(step, context)
                if ros_action:
                    ros_actions.append(ros_action)

            sequence = ActionSequence(
                actions=ros_actions,
                original_command=original_command,
                context=context,
                generated_at=str(asyncio.get_event_loop().time())
            )

            self.logger.info(f"Generated {len(ros_actions)} ROS 2 actions from {len(action_steps)} LLM steps",
                           component="ActionSequenceGenerator")

            return sequence

        except Exception as e:
            self.error_handler.handle_exception(e, "ActionSequenceGenerator.generate_action_sequence")
            # Return empty sequence on error
            return ActionSequence([], original_command, context or {}, str(asyncio.get_event_loop().time()))

    def _convert_action_step(self, action_step: ActionStep, context: Dict[str, Any]) -> Optional[ROS2Action]:
        """
        Convert a single LLM action step to a ROS 2 action
        """
        try:
            action_type = action_step.action_type.lower()

            # Find the appropriate mapping
            mapping = None
            for key, value in self.action_mapping.items():
                if key in action_type or key.replace('_', '') in action_type.replace('_', ''):
                    mapping = value
                    break

            if not mapping:
                self.logger.warning(f"No mapping found for action type: {action_type}",
                                  component="ActionSequenceGenerator")
                # Create a generic action for unmapped types
                return ROS2Action(
                    action_type=ROS2ActionType.COMMUNICATION,  # Default type
                    service_or_action_name=f"/unknown_action_{action_type}",
                    parameters=action_step.parameters,
                    description=f"Unknown action: {action_step.description}"
                )

            # Map parameters according to the mapping
            mapped_params = self._map_parameters(
                action_step.parameters,
                mapping["parameter_mapping"],
                context
            )

            return ROS2Action(
                action_type=mapping["action_type"],
                service_or_action_name=mapping["service"],
                parameters=mapped_params,
                description=action_step.description
            )

        except Exception as e:
            self.error_handler.handle_exception(e, "ActionSequenceGenerator._convert_action_step")
            return None

    def _map_parameters(self, original_params: Dict[str, Any],
                       param_mapping: Dict[str, str],
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map parameters from LLM format to ROS 2 format
        """
        mapped_params = {}

        for llm_param, ros_param in param_mapping.items():
            if llm_param in original_params:
                value = original_params[llm_param]

                # Handle nested parameter mapping (e.g., "pose.position.x")
                if '.' in ros_param:
                    self._set_nested_param(mapped_params, ros_param, value)
                else:
                    mapped_params[ros_param] = value

        # Add any additional context parameters that might be needed
        mapped_params.update(self._get_context_parameters(context))

        return mapped_params

    def _set_nested_param(self, params_dict: Dict[str, Any], param_path: str, value: Any):
        """
        Set a nested parameter using dot notation (e.g., "pose.position.x")
        """
        keys = param_path.split('.')
        current = params_dict

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _get_context_parameters(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant parameters from context
        """
        context_params = {}

        # Add robot state information
        if 'robot_state' in context:
            robot_state = context['robot_state']
            if 'position' in robot_state:
                context_params['current_position'] = robot_state['position']
            if 'orientation' in robot_state:
                context_params['current_orientation'] = robot_state['orientation']

        # Add environment information
        if 'environment' in context:
            env = context['environment']
            if 'objects' in env:
                context_params['environment_objects'] = env['objects']
            if 'locations' in env:
                context_params['environment_locations'] = env['locations']

        return context_params

    def validate_action_sequence(self, sequence: ActionSequence) -> Dict[str, Any]:
        """
        Validate that the action sequence is executable
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "executable": True
        }

        try:
            if not sequence.actions:
                validation_result["valid"] = False
                validation_result["errors"].append("Action sequence is empty")
                validation_result["executable"] = False
                return validation_result

            # Check each action in the sequence
            for i, action in enumerate(sequence.actions):
                # Validate action type
                if not isinstance(action.action_type, ROS2ActionType):
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Action {i}: Invalid action type")
                    validation_result["executable"] = False

                # Validate service/action name
                if not action.service_or_action_name or not isinstance(action.service_or_action_name, str):
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Action {i}: Invalid service/action name")
                    validation_result["executable"] = False

                # Validate parameters
                if not isinstance(action.parameters, dict):
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Action {i}: Parameters must be a dictionary")
                    validation_result["executable"] = False

            # Check for potential conflicts in the sequence
            conflicts = self._check_action_conflicts(sequence.actions)
            if conflicts:
                validation_result["warnings"].extend(conflicts)

        except Exception as e:
            self.error_handler.handle_exception(e, "ActionSequenceGenerator.validate_action_sequence")
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")
            validation_result["executable"] = False

        return validation_result

    def _check_action_conflicts(self, actions: List[ROS2Action]) -> List[str]:
        """
        Check for potential conflicts between actions in a sequence
        """
        conflicts = []

        # Example conflict checks (in a real system, these would be more sophisticated)
        for i, action in enumerate(actions):
            # Check for navigation followed immediately by manipulation without verification
            if (action.action_type == ROS2ActionType.NAVIGATION and
                i + 1 < len(actions) and
                actions[i + 1].action_type in [ROS2ActionType.MANIPULATION, ROS2ActionType.GRASPING]):
                conflicts.append(f"Navigation at index {i} followed by manipulation - consider adding verification step")

        return conflicts

    def optimize_action_sequence(self, sequence: ActionSequence) -> ActionSequence:
        """
        Optimize the action sequence for better execution
        """
        try:
            optimized_actions = []
            actions = sequence.actions

            # Remove redundant actions
            i = 0
            while i < len(actions):
                current_action = actions[i]

                # Check if this action is redundant with the next one
                if (i + 1 < len(actions) and
                    self._are_actions_redundant(current_action, actions[i + 1])):
                    # Skip the current action as it's redundant
                    i += 2  # Skip both actions
                    continue

                optimized_actions.append(current_action)
                i += 1

            optimized_sequence = ActionSequence(
                actions=optimized_actions,
                original_command=sequence.original_command,
                context=sequence.context,
                generated_at=str(asyncio.get_event_loop().time())
            )

            if len(optimized_actions) < len(sequence.actions):
                self.logger.info(f"Optimized sequence: {len(sequence.actions)} → {len(optimized_actions)} actions",
                               component="ActionSequenceGenerator")

            return optimized_sequence

        except Exception as e:
            self.error_handler.handle_exception(e, "ActionSequenceGenerator.optimize_action_sequence")
            # Return original sequence on error
            return sequence

    def _are_actions_redundant(self, action1: ROS2Action, action2: ROS2Action) -> bool:
        """
        Check if two actions are redundant
        """
        # For now, just check if they're the same action with same parameters
        # In a real system, this would be more sophisticated
        return (action1.action_type == action2.action_type and
                action1.service_or_action_name == action2.service_or_action_name and
                action1.parameters == action2.parameters)

    def generate_ros2_execution_code(self, sequence: ActionSequence) -> str:
        """
        Generate ROS 2 Python code that would execute the action sequence
        This is primarily for demonstration and debugging
        """
        code_lines = [
            "# Generated ROS 2 action sequence execution code",
            "import rclpy",
            "from rclpy.node import Node",
            "from rclpy.action import ActionClient",
            "import time",
            "",
            "class ActionSequenceExecutor(Node):",
            "    def __init__(self):",
            "        super().__init__('action_sequence_executor')",
            "        # Initialize action clients based on sequence",
            ""
        ]

        # Add action client declarations
        for action in sequence.actions:
            client_name = f"self.{action.service_or_action_name.replace('/', '_').replace(' ', '_')}_client"
            code_lines.append(f"        {client_name} = None  # TODO: Initialize with proper action type")

        code_lines.extend([
            "",
            "    async def execute_sequence(self):",
            f"        # Original command: {sequence.original_command}",
            "        try:"
        ])

        # Add execution code for each action
        for i, action in enumerate(sequence.actions):
            code_lines.append(f"            # Action {i + 1}: {action.description}")
            code_lines.append(f"            await self.execute_action_{i + 1}()")
            code_lines.append("            time.sleep(0.5)  # Brief pause between actions")
            code_lines.append("")

        code_lines.extend([
            "        except Exception as e:",
            "            self.get_logger().error(f'Error executing sequence: {e}')",
            "",
            "    # Action execution methods would be implemented here",
            "    # ... (method implementations)",
            "",
            "def main():",
            "    rclpy.init()",
            "    executor = ActionSequenceExecutor()",
            "    # Execute the sequence",
            "    # rclpy.spin(executor)",  # Commented out to avoid blocking
            "    executor.destroy_node()",
            "    rclpy.shutdown()",
            "",
            "if __name__ == '__main__':",
            "    main()"
        ])

        return "\n".join(code_lines)


class ROS2ActionExecutor:
    """
    Executes ROS 2 action sequences in a real ROS 2 environment
    """

    def __init__(self, node: Optional[Node] = None):
        self.node = node or Node("action_executor")
        self.logger = VLALogger("ROS2ActionExecutor")
        self.error_handler = ErrorHandler(self.logger)

    async def execute_sequence(self, sequence: ActionSequence,
                             on_progress: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Execute a complete action sequence
        """
        if not ROS_AVAILABLE:
            raise RuntimeError("ROS 2 is not available. Cannot execute actions.")

        results = {
            "success": True,
            "executed_actions": [],
            "failed_actions": [],
            "total_time": 0.0
        }

        start_time = asyncio.get_event_loop().time()

        try:
            for i, action in enumerate(sequence.actions):
                if on_progress:
                    on_progress(i, len(sequence.actions), action.description)

                try:
                    action_result = await self.execute_single_action(action)
                    results["executed_actions"].append({
                        "index": i,
                        "action": action.description,
                        "success": action_result["success"],
                        "details": action_result
                    })

                    if not action_result["success"]:
                        results["success"] = False
                        results["failed_actions"].append({
                            "index": i,
                            "action": action.description,
                            "error": action_result.get("error", "Unknown error")
                        })

                        # Handle failure based on retry policy
                        if action.retry_count > 0:
                            # Retry logic would go here
                            pass
                        else:
                            # If action failed and no retries left, stop execution
                            break

                except Exception as e:
                    self.error_handler.handle_exception(e, f"ROS2ActionExecutor.execute_sequence.action_{i}")
                    results["success"] = False
                    results["failed_actions"].append({
                        "index": i,
                        "action": action.description,
                        "error": str(e)
                    })

        except Exception as e:
            self.error_handler.handle_exception(e, "ROS2ActionExecutor.execute_sequence")
            results["success"] = False
            results["failed_actions"].append({
                "index": -1,
                "action": "Sequence execution",
                "error": str(e)
            })

        results["total_time"] = asyncio.get_event_loop().time() - start_time
        return results

    async def execute_single_action(self, action: ROS2Action) -> Dict[str, Any]:
        """
        Execute a single ROS 2 action
        """
        try:
            # This is a simplified execution model
            # In a real implementation, this would call actual ROS 2 services/actions
            self.logger.info(f"Executing action: {action.service_or_action_name}",
                           component="ROS2ActionExecutor")

            # Simulate action execution
            await asyncio.sleep(0.1)  # Simulate processing time

            # For demonstration, return success
            # In real implementation, this would interact with ROS 2
            return {
                "success": True,
                "action_type": action.action_type.value,
                "service_called": action.service_or_action_name,
                "parameters_used": action.parameters,
                "execution_time": 0.1
            }

        except Exception as e:
            self.error_handler.handle_exception(e, "ROS2ActionExecutor.execute_single_action")
            return {
                "success": False,
                "error": str(e),
                "action_type": action.action_type.value
            }


# Example usage and testing
async def test_action_sequence_generator():
    """
    Test the action sequence generator with sample LLM output
    """
    print("Testing Action Sequence Generator")
    print("=" * 40)

    generator = ActionSequenceGenerator()

    # Sample LLM-generated action steps (as if from our LLM planning)
    sample_action_steps = [
        ActionStep(
            action_type="detect_object",
            parameters={"object_type": "cup", "color": "red", "location": "table"},
            description="Detect a red cup on the table"
        ),
        ActionStep(
            action_type="move_to",
            parameters={"target_location": "table_1", "x": 1.0, "y": 2.0, "z": 0.0},
            description="Move to the table where the cup is located"
        ),
        ActionStep(
            action_type="grasp",
            parameters={"object_id": "red_cup", "grasp_type": "top_grasp", "force": 10.0},
            description="Grasp the red cup"
        ),
        ActionStep(
            action_type="navigate",
            parameters={"target_location": "kitchen_counter", "x": 3.0, "y": 1.0, "z": 0.0},
            description="Navigate to kitchen counter"
        ),
        ActionStep(
            action_type="place",
            parameters={"object": "red_cup", "destination": "kitchen_counter"},
            description="Place the cup on the kitchen counter"
        )
    ]

    # Generate action sequence
    sequence = generator.generate_action_sequence(
        action_steps=sample_action_steps,
        original_command="Move the red cup from the table to the kitchen counter",
        context={
            "robot_state": {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            },
            "environment": {
                "objects": ["red_cup", "table", "kitchen_counter"],
                "locations": ["table_1", "kitchen_counter"]
            }
        }
    )

    print(f"\n1. Generated {len(sequence.actions)} ROS 2 actions")
    for i, action in enumerate(sequence.actions):
        print(f"   {i+1}. {action.description}")
        print(f"      Type: {action.action_type.value}")
        print(f"      Service: {action.service_or_action_name}")
        print(f"      Params: {action.parameters}")

    # Validate the sequence
    validation = generator.validate_action_sequence(sequence)
    print(f"\n2. Validation result: {'VALID' if validation['valid'] else 'INVALID'}")
    print(f"   Executable: {validation['executable']}")
    if validation['errors']:
        print(f"   Errors: {validation['errors']}")
    if validation['warnings']:
        print(f"   Warnings: {validation['warnings']}")

    # Optimize the sequence
    optimized = generator.optimize_action_sequence(sequence)
    print(f"\n3. Optimization: {len(sequence.actions)} → {len(optimized.actions)} actions")

    # Generate example ROS 2 code
    code = generator.generate_ros2_execution_code(sequence)
    print(f"\n4. Generated ROS 2 execution code ({len(code.split())} lines)")

    print(f"\nAction Sequence Generator test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_action_sequence_generator())