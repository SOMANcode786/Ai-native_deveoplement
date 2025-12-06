"""
LLM Prompt Engineering Utilities for Vision-Language-Action (VLA) System

This module provides utilities for crafting effective prompts for large language models
in the context of robotics and VLA applications.
"""

import json
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging


class PromptRole(Enum):
    """Roles for different parts of a prompt"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class RobotActionType(Enum):
    """Types of robot actions for prompt engineering"""
    NAVIGATION = "navigation"
    MANIPULATION = "manipulation"
    PERCEPTION = "perception"
    PLANNING = "planning"
    COMMUNICATION = "communication"


@dataclass
class PromptTemplate:
    """Template for structured prompts"""
    name: str
    description: str
    role: PromptRole
    template: str
    variables: List[str]
    action_type: Optional[RobotActionType] = None


class PromptEngineeringUtilities:
    """
    Utilities for crafting effective prompts for LLMs in robotics contexts
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates = self._initialize_templates()
        self.validators = self._initialize_validators()

    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize common prompt templates for VLA applications"""
        return {
            "robotics_command_planning": PromptTemplate(
                name="robotics_command_planning",
                description="Plan robot actions from natural language commands",
                role=PromptRole.USER,
                template="""
                You are a robotics planning assistant. Convert the following natural language command into a sequence of specific robotic actions.

                Context: {context}
                Command: {command}

                Respond with a JSON array of action steps, where each step has:
                - action_type: The type of action (e.g., "move_to", "grasp", "detect_object", "navigate")
                - parameters: A dictionary of parameters needed for the action
                - description: A human-readable description of the action

                Example response format:
                [
                    {{
                        "action_type": "detect_object",
                        "parameters": {{"object_type": "cup", "color": "red"}},
                        "description": "Detect a red cup on the table"
                    }},
                    {{
                        "action_type": "move_to",
                        "parameters": {{"target_location": "table_1"}},
                        "description": "Move to the table where the cup is located"
                    }}
                ]

                Respond only with the JSON array, no additional text.
                """,
                variables=["context", "command"],
                action_type=RobotActionType.PLANNING
            ),
            "object_identification": PromptTemplate(
                name="object_identification",
                description="Identify and describe objects in the environment",
                role=PromptRole.USER,
                template="""
                You are a computer vision assistant. Analyze the following image and identify objects relevant to the task.

                Task: {task}
                Environment context: {environment_context}

                Provide a structured response with:
                - object_list: Array of objects with properties (name, position, color, size)
                - relevant_objects: Objects relevant to the task
                - potential_obstacles: Objects that might interfere with task execution

                Format as JSON with these exact keys.
                """,
                variables=["task", "environment_context"],
                action_type=RobotActionType.PERCEPTION
            ),
            "navigation_planning": PromptTemplate(
                name="navigation_planning",
                description="Plan navigation paths and avoid obstacles",
                role=PromptRole.USER,
                template="""
                You are a navigation planning assistant. Given the current robot position and destination, plan a safe path.

                Current position: {current_position}
                Destination: {destination}
                Environment map: {environment_map}
                Obstacles: {obstacles}

                Provide:
                - path: Array of waypoints from start to destination
                - safety_assessment: Potential risks along the path
                - alternative_routes: Other possible paths if primary path is blocked

                Format as JSON with these exact keys.
                """,
                variables=["current_position", "destination", "environment_map", "obstacles"],
                action_type=RobotActionType.NAVIGATION
            ),
            "manipulation_planning": PromptTemplate(
                name="manipulation_planning",
                description="Plan manipulation actions for objects",
                role=PromptRole.USER,
                template="""
                You are a manipulation planning assistant. Plan the sequence of actions needed to manipulate an object.

                Object: {object_description}
                Task: {manipulation_task}
                Robot capabilities: {robot_capabilities}
                Safety constraints: {safety_constraints}

                Provide:
                - approach_sequence: Steps to approach the object safely
                - grasp_plan: How to grasp the object based on its properties
                - manipulation_steps: Actions to achieve the manipulation goal
                - verification_steps: How to verify successful manipulation

                Format as JSON with these exact keys.
                """,
                variables=["object_description", "manipulation_task", "robot_capabilities", "safety_constraints"],
                action_type=RobotActionType.MANIPULATION
            )
        }

    def _initialize_validators(self) -> Dict[str, Callable]:
        """Initialize validators for prompt outputs"""
        return {
            "action_sequence": self._validate_action_sequence,
            "object_identification": self._validate_object_identification,
            "navigation_plan": self._validate_navigation_plan,
            "manipulation_plan": self._validate_manipulation_plan
        }

    def create_prompt_from_template(self, template_name: str, **kwargs) -> str:
        """Create a prompt by filling a template with provided variables"""
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = self.templates[template_name]

        # Check that all required variables are provided
        missing_vars = set(template.variables) - set(kwargs.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")

        try:
            return template.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Error filling template '{template_name}': {e}")

    def create_structured_prompt(self, system_message: str, user_message: str,
                               context: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Create a structured prompt with system, user, and optional context messages"""
        messages = []

        # Add system message
        messages.append({
            "role": PromptRole.SYSTEM.value,
            "content": system_message
        })

        # Add context if provided
        if context:
            context_str = json.dumps(context, indent=2)
            messages.append({
                "role": PromptRole.USER.value,
                "content": f"Context information:\n{context_str}"
            })

        # Add user message
        messages.append({
            "role": PromptRole.USER.value,
            "content": user_message
        })

        return messages

    def _validate_action_sequence(self, response: str) -> Dict[str, Any]:
        """Validate an action sequence response from an LLM"""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return {"valid": False, "error": "No JSON array found in response"}

            json_str = json_match.group(0)
            action_sequence = json.loads(json_str)

            if not isinstance(action_sequence, list):
                return {"valid": False, "error": "Response is not a JSON array"}

            for i, action in enumerate(action_sequence):
                if not isinstance(action, dict):
                    return {"valid": False, "error": f"Action {i} is not a dictionary"}

                required_keys = ["action_type", "parameters", "description"]
                missing_keys = [key for key in required_keys if key not in action]
                if missing_keys:
                    return {"valid": False, "error": f"Action {i} missing keys: {missing_keys}"}

            return {"valid": True, "action_sequence": action_sequence}

        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {e}"}

    def _validate_object_identification(self, response: str) -> Dict[str, Any]:
        """Validate object identification response"""
        try:
            data = json.loads(response)
            required_keys = ["object_list", "relevant_objects", "potential_obstacles"]

            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return {"valid": False, "error": f"Missing keys: {missing_keys}"}

            return {"valid": True, "data": data}

        except json.JSONDecodeError:
            return {"valid": False, "error": "Invalid JSON"}

    def _validate_navigation_plan(self, response: str) -> Dict[str, Any]:
        """Validate navigation plan response"""
        try:
            data = json.loads(response)
            required_keys = ["path", "safety_assessment"]

            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return {"valid": False, "error": f"Missing keys: {missing_keys}"}

            return {"valid": True, "data": data}

        except json.JSONDecodeError:
            return {"valid": False, "error": "Invalid JSON"}

    def _validate_manipulation_plan(self, response: str) -> Dict[str, Any]:
        """Validate manipulation plan response"""
        try:
            data = json.loads(response)
            required_keys = ["approach_sequence", "grasp_plan", "manipulation_steps", "verification_steps"]

            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return {"valid": False, "error": f"Missing keys: {missing_keys}"}

            return {"valid": True, "data": data}

        except json.JSONDecodeError:
            return {"valid": False, "error": "Invalid JSON"}

    def validate_response(self, response: str, validator_type: str) -> Dict[str, Any]:
        """Validate LLM response using the appropriate validator"""
        if validator_type not in self.validators:
            return {"valid": False, "error": f"Unknown validator type: {validator_type}"}

        validator = self.validators[validator_type]
        return validator(response)

    def create_robust_prompt(self, intent: str, context: Dict[str, Any],
                           safety_constraints: Optional[List[str]] = None,
                           formatting_instructions: Optional[str] = None) -> str:
        """Create a robust prompt with safety and formatting considerations"""
        base_prompt = f"""
        As a robotics planning assistant, your task is to convert high-level commands into executable robotic actions.

        Intent: {intent}

        Context:
        {json.dumps(context, indent=2)}

        """

        if safety_constraints:
            base_prompt += f"\nSafety Constraints:\n"
            for i, constraint in enumerate(safety_constraints, 1):
                base_prompt += f"{i}. {constraint}\n"

        base_prompt += f"""
        Requirements:
        - Provide a sequence of specific, executable actions that a robot can perform
        - Consider the context and constraints provided
        - Ensure all actions are safe and feasible
        """

        if formatting_instructions:
            base_prompt += f"\nFormatting Instructions:\n{formatting_instructions}"

        base_prompt += f"""
        Respond in the required format, including all necessary details for robotic execution.
        """

        return base_prompt

    def create_chain_of_thought_prompt(self, command: str, context: Dict[str, Any]) -> str:
        """Create a prompt that encourages step-by-step reasoning"""
        return f"""
        As a robotics planning assistant, break down the following command into logical steps using chain of thought reasoning.

        Command: {command}

        Context:
        {json.dumps(context, indent=2)}

        Think through this step by step:
        1. What is the goal?
        2. What information do I have about the environment?
        3. What are the intermediate steps needed?
        4. What actions are required for each step?
        5. How can I verify success at each stage?

        Then provide the final action sequence in the required JSON format.
        """

    def create_few_shot_prompt(self, command: str, examples: List[Dict[str, str]]) -> str:
        """Create a few-shot learning prompt with examples"""
        prompt = "Here are examples of converting commands to action sequences:\n\n"

        for i, example in enumerate(examples, 1):
            prompt += f"Example {i}:\n"
            prompt += f"Command: {example['command']}\n"
            prompt += f"Action Sequence: {example['action_sequence']}\n\n"

        prompt += f"Now process this command:\n{command}\n\n"
        prompt += "Provide the action sequence in the same format as the examples."

        return prompt

    def create_context_aware_prompt(self, command: str, short_term_memory: List[Dict[str, Any]],
                                  long_term_context: Dict[str, Any]) -> str:
        """Create a prompt that incorporates both short and long-term context"""
        prompt = f"Command: {command}\n\n"

        if short_term_memory:
            prompt += "Recent interactions:\n"
            for i, interaction in enumerate(short_term_memory[-3:], 1):  # Last 3 interactions
                prompt += f"{i}. {interaction.get('command', '')} -> {interaction.get('result', '')}\n"
            prompt += "\n"

        if long_term_context:
            prompt += f"Environment context:\n{json.dumps(long_term_context, indent=2)}\n\n"

        prompt += """
        Consider the recent interactions and environment context when planning actions.
        Maintain consistency with previous decisions where appropriate.
        """

        return prompt


class RoboticsPromptBuilder:
    """High-level builder for creating complex robotics prompts"""

    def __init__(self):
        self.utilities = PromptEngineeringUtilities()
        self.logger = logging.getLogger(__name__)

    def build_command_planning_prompt(self, natural_command: str, environment_context: Dict[str, Any],
                                    robot_capabilities: Optional[Dict[str, Any]] = None,
                                    safety_constraints: Optional[List[str]] = None) -> str:
        """Build a comprehensive command planning prompt"""
        context = {
            "environment": environment_context,
            "robot_capabilities": robot_capabilities or {},
            "safety_constraints": safety_constraints or []
        }

        return self.utilities.create_robust_prompt(
            intent=natural_command,
            context=context,
            safety_constraints=safety_constraints,
            formatting_instructions="Respond with a JSON array of action steps, each with action_type, parameters, and description."
        )

    def build_perception_prompt(self, task: str, image_description: str,
                              environment_context: Dict[str, Any]) -> str:
        """Build a perception-focused prompt"""
        return f"""
        You are a computer vision assistant for a robotics system.

        Task: {task}
        Image Description: {image_description}
        Environment Context: {json.dumps(environment_context, indent=2)}

        Analyze the scene and provide structured information about objects, their properties, and their relevance to the task.
        Respond in JSON format with clearly defined fields.
        """

    def build_navigation_prompt(self, start_location: str, end_location: str,
                              map_data: Dict[str, Any], dynamic_obstacles: List[Dict[str, Any]]) -> str:
        """Build a navigation-focused prompt"""
        return f"""
        You are a navigation planning assistant for a mobile robot.

        Route: {start_location} → {end_location}
        Static Map: {json.dumps(map_data, indent=2)}
        Dynamic Obstacles: {json.dumps(dynamic_obstacles, indent=2)}

        Plan a safe and efficient path considering both static and dynamic obstacles.
        Provide alternative routes if the primary path is blocked.
        """

    def add_safety_layer(self, prompt: str, safety_requirements: List[str]) -> str:
        """Add safety considerations to any prompt"""
        safety_text = "\n\nSAFETY REQUIREMENTS:\n"
        for req in safety_requirements:
            safety_text += f"- {req}\n"

        return prompt + safety_text

    def optimize_for_clarity(self, prompt: str) -> str:
        """Optimize prompt for LLM understanding and response quality"""
        # Remove excessive whitespace
        prompt = re.sub(r'\n\s+\n', '\n\n', prompt)
        # Ensure clear section separation
        prompt = re.sub(r'\n([A-Z][A-Z\s]+):', r'\n\n\1:', prompt)
        # Add emphasis to important instructions
        prompt = prompt.replace("Respond in JSON format", "**Respond in JSON format**")
        prompt = prompt.replace("Required format", "**Required format**")

        return prompt


# Example usage and testing
def create_robotics_prompts_demo():
    """Demonstrate the prompt engineering utilities"""
    print("Prompt Engineering Utilities Demo")
    print("=" * 40)

    utilities = PromptEngineeringUtilities()
    builder = RoboticsPromptBuilder()

    # Example 1: Using template
    print("\n1. Using template:")
    template_prompt = utilities.create_prompt_from_template(
        "robotics_command_planning",
        context="The robot is in a kitchen environment with tables, chairs, and a counter.",
        command="Move the red cup from the table to the counter."
    )
    print(f"Template prompt created: {len(template_prompt)} characters")

    # Example 2: Creating structured prompt
    print("\n2. Structured prompt:")
    structured = utilities.create_structured_prompt(
        system_message="You are a helpful robotics assistant.",
        user_message="Pick up the green block and place it on the blue mat.",
        context={
            "robot_position": "home",
            "objects": ["green_block", "blue_mat"],
            "workspace": "tabletop"
        }
    )
    print(f"Structured prompt created with {len(structured)} messages")

    # Example 3: Building command planning prompt
    print("\n3. Command planning prompt:")
    command_prompt = builder.build_command_planning_prompt(
        natural_command="Clean up the table by putting the books in the shelf",
        environment_context={
            "objects_on_table": ["book1", "book2", "cup"],
            "shelf_location": "north_wall",
            "robot_arm_range": 1.0
        },
        robot_capabilities={
            "grasping": True,
            "navigation": True,
            "object_recognition": True
        },
        safety_constraints=[
            "Do not drop objects",
            "Avoid collisions with furniture",
            "Stop if person enters workspace"
        ]
    )
    print(f"Command planning prompt created: {len(command_prompt)} characters")

    # Example 4: Chain of thought prompt
    print("\n4. Chain of thought prompt:")
    cot_prompt = utilities.create_chain_of_thought_prompt(
        command="Organize the desk by sorting papers into piles",
        context={
            "desk_items": ["papers", "pens", "notebook"],
            "available_spaces": ["left_side", "right_side", "drawer"]
        }
    )
    print(f"Chain of thought prompt created: {len(cot_prompt)} characters")

    print("\nPrompt engineering utilities ready for VLA system integration!")


if __name__ == "__main__":
    create_robotics_prompts_demo()