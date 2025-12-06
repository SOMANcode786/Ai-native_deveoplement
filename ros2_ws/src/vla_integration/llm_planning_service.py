#!/usr/bin/env python3
"""
ROS 2 Service for LLM Planning in Vision-Language-Action (VLA) System

This service integrates large language models with ROS 2 for high-level
robotic planning and task decomposition.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy

# Import custom service definition (would be generated from .srv file)
from vla_interfaces.srv import VLAPrompt  # Custom service
from vla_interfaces.action import VLACommand  # Custom action

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

# Import our LLM integration modules
from src.llm_integration import LLMManager, LLMConfig, LLMProvider, ActionStep
from src.llm_integration.prompt_engineering import PromptEngineeringUtilities, RoboticsPromptBuilder
from src.error_handling import ErrorHandler, VLALogger, VLAException, VLAErrorType
from src.vla_config import get_vla_config


class LLMPlanningService(Node):
    """
    ROS 2 Service Node that handles LLM-based planning for the VLA system
    Provides high-level planning capabilities to convert natural language commands
    into structured action sequences
    """

    def __init__(self):
        super().__init__('llm_planning_service')

        # Initialize logging
        self.logger = VLALogger('LLMPlanningService')
        self.error_handler = ErrorHandler(self.logger)

        # Node parameters
        self.declare_parameter('llm_provider', 'openai')
        self.declare_parameter('llm_model', 'gpt-3.5-turbo')
        self.declare_parameter('temperature', 0.7)
        self.declare_parameter('max_tokens', 1000)

        # Get parameters
        llm_provider_str = self.get_parameter('llm_provider').get_parameter_value().string_value
        llm_model = self.get_parameter('llm_model').get_parameter_value().string_value
        temperature = self.get_parameter('llm_temperature').get_parameter_value().double_value
        max_tokens = self.get_parameter('llm_max_tokens').get_parameter_value().integer_value

        try:
            # Initialize LLM manager
            vla_config = get_vla_config()
            llm_config = LLMConfig(
                provider=LLMProvider(vla_config.llm_provider),
                api_key=vla_config.llm_api_key,
                model=vla_config.llm_model,
                temperature=vla_config.llm_temperature,
                max_tokens=vla_config.llm_max_tokens,
                timeout=vla_config.llm_timeout
            )

            self.llm_manager = LLMManager(llm_config)
            self.logger.info("LLM Manager initialized", component="LLMPlanningService")

            # Initialize prompt engineering utilities
            self.prompt_utils = PromptEngineeringUtilities()
            self.prompt_builder = RoboticsPromptBuilder()
            self.logger.info("Prompt engineering utilities initialized", component="LLMPlanningService")

        except Exception as e:
            self.error_handler.handle_exception(e, "LLMPlanningService.__init__")
            raise

        # Create service
        self.planning_srv = self.create_service(
            VLAPrompt,  # Custom service for planning requests
            'vla/llm_plan_command',
            self.plan_command_callback
        )

        # Create action server for long-running planning tasks
        # Note: In a real implementation, you would use action server
        # For now, we'll just log that this would be implemented

        self.logger.info("LLM Planning Service initialized", component="LLMPlanningService")

    def plan_command_callback(self, request: VLAPrompt.Request, response: VLAPrompt.Response):
        """
        Service callback for planning commands with LLM
        """
        try:
            self.logger.info(f"Received planning request: {request.natural_language_command[:50]}...",
                           component="LLMPlanningService")

            # Process the command with context
            command = request.natural_language_command
            context = request.context

            # Use asyncio to call the async planning method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                action_sequence = loop.run_until_complete(
                    self.plan_action_sequence_async(command, context)
                )
            finally:
                loop.close()

            if action_sequence:
                # Convert action sequence to response format
                response.success = True
                response.message = f"Planned {len(action_sequence)} actions"
                response.action_sequence = [step.description for step in action_sequence]

                self.logger.info(f"Planned {len(action_sequence)} actions for command: {command[:30]}...",
                               component="LLMPlanningService")
            else:
                response.success = False
                response.message = "Failed to generate action sequence"
                response.action_sequence = []

        except Exception as e:
            self.error_handler.handle_exception(e, "LLMPlanningService.plan_command_callback")
            response.success = False
            response.message = f"Error in planning: {str(e)}"
            response.action_sequence = []

        return response

    async def plan_action_sequence_async(self, command: str, context: str = "") -> Optional[list]:
        """
        Plan action sequence asynchronously using LLM
        """
        try:
            # Plan the action sequence using LLM manager
            action_steps = await self.llm_manager.plan_action_sequence(command, context)

            # Validate the plan
            is_valid = await self.llm_manager.validate_plan(action_steps)

            if not is_valid:
                self.logger.warning("Generated action sequence failed validation", component="LLMPlanningService")
                return None

            self.logger.info(f"Generated valid action sequence with {len(action_steps)} steps",
                           component="LLMPlanningService")
            return action_steps

        except Exception as e:
            self.error_handler.handle_exception(e, "LLMPlanningService.plan_action_sequence_async")
            return None

    def create_robotics_prompt(self, command: str, environment_context: Dict[str, Any]) -> str:
        """
        Create a specialized robotics prompt for the given command
        """
        try:
            # Use the prompt builder to create a context-aware prompt
            prompt = self.prompt_builder.build_command_planning_prompt(
                natural_command=command,
                environment_context=environment_context,
                robot_capabilities=self.get_robot_capabilities(),
                safety_constraints=self.get_safety_constraints()
            )

            self.logger.info("Created specialized robotics prompt", component="LLMPlanningService")
            return prompt

        except Exception as e:
            self.error_handler.handle_exception(e, "LLMPlanningService.create_robotics_prompt")
            # Fallback to simple prompt
            return f"Convert this command to robotic actions: {command}"

    def get_robot_capabilities(self) -> Dict[str, Any]:
        """
        Get robot capabilities for prompt context
        In a real implementation, this would query the robot's actual capabilities
        """
        return {
            "navigation": True,
            "manipulation": True,
            "object_recognition": True,
            "grasping": True,
            "speech": True,
            "arm_range_meters": 1.0,
            "max_payload_kg": 2.0
        }

    def get_safety_constraints(self) -> list:
        """
        Get safety constraints for prompt context
        """
        return [
            "Avoid collisions with humans and obstacles",
            "Do not lift objects beyond payload capacity",
            "Stop immediately if safety sensor is triggered",
            "Maintain safe distance from edges and drops",
            "Verify object stability before manipulation"
        ]

    def validate_action_sequence(self, action_sequence: list) -> Dict[str, Any]:
        """
        Validate that the action sequence is feasible for the robot
        """
        try:
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": []
            }

            if not action_sequence:
                validation_results["valid"] = False
                validation_results["errors"].append("Action sequence is empty")
                return validation_results

            # Check each action in the sequence
            for i, action in enumerate(action_sequence):
                # In a real implementation, this would validate against robot capabilities
                if not hasattr(action, 'action_type') or not action.action_type:
                    validation_results["valid"] = False
                    validation_results["errors"].append(f"Action {i} missing action_type")

                # Add other validation checks as needed
                # - Check if action type is supported
                # - Check if parameters are valid
                # - Check for action conflicts
                # - Check for resource constraints

            return validation_results

        except Exception as e:
            self.error_handler.handle_exception(e, "LLMPlanningService.validate_action_sequence")
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": []
            }


class LLMPlanningClient:
    """
    Client class for interacting with the LLM Planning Service
    Provides convenient methods for requesting planning services
    """

    def __init__(self, node: Node):
        self.node = node
        self.logger = VLALogger('LLMPlanningClient')

        # Create client for the planning service
        self.planning_client = self.node.create_client(VLAPrompt, 'vla/llm_plan_command')

        # Wait for service to be available
        while not self.planning_client.wait_for_service(timeout_sec=1.0):
            self.logger.info('LLM planning service not available, waiting again...', component="LLMPlanningClient")

    async def plan_command(self, command: str, context: str = "") -> Optional[list]:
        """
        Request action planning for a command
        """
        try:
            # Create request
            request = VLAPrompt.Request()
            request.natural_language_command = command
            request.context = context

            # Call service
            future = self.planning_client.call_async(request)
            await future

            response = future.result()

            if response.success:
                self.logger.info(f"Successfully planned command: {command[:30]}...", component="LLMPlanningClient")
                # Convert response action sequence to internal format
                return response.action_sequence
            else:
                self.logger.error(f"Planning failed: {response.message}", component="LLMPlanningClient")
                return None

        except Exception as e:
            self.logger.error(f"Error calling planning service: {e}", component="LLMPlanningClient")
            return None


def main(args=None):
    """Main function to run the LLM planning service"""
    rclpy.init(args=args)

    try:
        node = LLMPlanningService()
        node.logger.info("Starting LLM Planning Service", component="LLMPlanningService")

        # Spin the node
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.logger.info("Interrupted by user", component="LLMPlanningService")
    except Exception as e:
        if 'node' in locals():
            node.error_handler.handle_exception(e, "LLMPlanningService.main")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


# Additional utilities for LLM planning in ROS 2 context
class ROS2LLMIntegration:
    """Integration utilities for LLMs with ROS 2"""

    @staticmethod
    def convert_ros_params_to_context(node: Node) -> Dict[str, Any]:
        """
        Convert ROS 2 parameters to context for LLM planning
        """
        try:
            context = {
                'node_name': node.get_name(),
                'namespace': node.get_namespace(),
                'parameters': {}
            }

            # Get all parameters from the node
            for param_name in node._parameters.keys():
                param_value = node.get_parameter(param_name).value
                context['parameters'][param_name] = param_value

            return context
        except Exception as e:
            node.get_logger().error(f"Error converting ROS params to context: {e}")
            return {}

    @staticmethod
    def validate_ros_service_availability(node: Node, service_name: str, service_type) -> bool:
        """
        Check if a ROS service is available
        """
        try:
            client = node.create_client(service_type, service_name)
            return client.wait_for_service(timeout_sec=1.0)
        except Exception:
            return False


# Example usage of the LLM planning service
async def example_usage():
    """
    Example of how to use the LLM planning service
    """
    print("LLM Planning Service Example")
    print("=" * 40)

    # This would normally run within a ROS 2 context
    # For demonstration, we'll show the conceptual usage:

    print("\n1. Service provides natural language to action planning")
    print("   Input: 'Move the red block to the blue area'")
    print("   Output: Sequence of ROS 2 actions")

    print("\n2. Supports various command types:")
    print("   - Navigation: 'Go to the kitchen'")
    print("   - Manipulation: 'Pick up the cup'")
    print("   - Complex tasks: 'Clean the table and return home'")

    print("\n3. Includes safety and validation:")
    print("   - Collision avoidance")
    print("   - Capability checking")
    print("   - Constraint validation")

    print("\nLLM Planning Service ready for VLA system integration!")


if __name__ == '__main__':
    # For now, just run the example
    # In a real ROS 2 environment, this would start the service
    asyncio.run(example_usage())