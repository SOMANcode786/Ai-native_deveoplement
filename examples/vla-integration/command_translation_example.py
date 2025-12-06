"""
Command Translation Examples for Vision-Language-Action (VLA) System

This module demonstrates how natural language commands are translated
into structured ROS 2 action sequences in the VLA system.
"""

import asyncio
import json
from typing import Dict, Any, List
from dataclasses import dataclass

# Import our VLA system components
from src.llm_integration import LLMManager, LLMConfig, LLMProvider, ActionStep
from src.llm_integration.prompt_engineering import PromptEngineeringUtilities, RoboticsPromptBuilder
from src.llm_integration.action_sequence_generator import ActionSequenceGenerator, ActionSequence
from src.error_handling import ErrorHandler, VLALogger


@dataclass
class CommandTranslationExample:
    """Represents a command translation example"""
    natural_language: str
    expected_actions: List[Dict[str, Any]]
    context: Dict[str, Any]
    description: str


class CommandTranslationExamples:
    """
    Examples and demonstrations of translating natural language commands
    to structured robotic actions
    """

    def __init__(self):
        self.logger = VLALogger("CommandTranslationExamples")
        self.error_handler = ErrorHandler(self.logger)
        self.prompt_utils = PromptEngineeringUtilities()
        self.prompt_builder = RoboticsPromptBuilder()
        self.action_generator = ActionSequenceGenerator()

        # Initialize with mock LLM manager for demonstration
        # In a real system, this would connect to an actual LLM
        try:
            from src.vla_config import get_vla_config
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
        except:
            # Create a basic LLM manager for demonstration
            llm_config = LLMConfig(
                provider=LLMProvider.OPENAI,  # Placeholder
                api_key="dummy-key",  # Placeholder
                model="gpt-3.5-turbo"
            )
            self.llm_manager = LLMManager(llm_config)

        self.examples = self._create_examples()

    def _create_examples(self) -> List[CommandTranslationExample]:
        """Create a set of command translation examples"""
        return [
            CommandTranslationExample(
                natural_language="Move the red cup from the table to the kitchen counter",
                expected_actions=[
                    {"action_type": "detect_object", "parameters": {"object_type": "cup", "color": "red"}},
                    {"action_type": "move_to", "parameters": {"target_location": "table"}},
                    {"action_type": "grasp", "parameters": {"object_id": "red_cup"}},
                    {"action_type": "move_to", "parameters": {"target_location": "kitchen_counter"}},
                    {"action_type": "place", "parameters": {"object_id": "red_cup", "location": "kitchen_counter"}}
                ],
                context={
                    "environment": {
                        "objects": ["red_cup", "table", "kitchen_counter"],
                        "locations": ["table", "kitchen_counter"]
                    },
                    "robot_capabilities": {
                        "navigation": True,
                        "manipulation": True,
                        "object_recognition": True
                    }
                },
                description="Basic object relocation task"
            ),
            CommandTranslationExample(
                natural_language="Clean up the table by removing all the books",
                expected_actions=[
                    {"action_type": "detect_object", "parameters": {"object_type": "book", "location": "table"}},
                    {"action_type": "move_to", "parameters": {"target_location": "table"}},
                    {"action_type": "grasp", "parameters": {"object_type": "book"}},
                    {"action_type": "move_to", "parameters": {"target_location": "shelf"}},
                    {"action_type": "place", "parameters": {"location": "shelf"}},
                    {"action_type": "detect_object", "parameters": {"object_type": "book", "location": "table"}}
                ],
                context={
                    "environment": {
                        "objects": ["book1", "book2", "book3", "table", "shelf"],
                        "locations": ["table", "shelf"]
                    },
                    "robot_capabilities": {
                        "navigation": True,
                        "manipulation": True,
                        "object_recognition": True
                    }
                },
                description="Multi-object cleanup task"
            ),
            CommandTranslationExample(
                natural_language="Go to the kitchen and wait for me there",
                expected_actions=[
                    {"action_type": "navigate", "parameters": {"target_location": "kitchen"}},
                    {"action_type": "wait", "parameters": {"duration": "indefinite"}}
                ],
                context={
                    "environment": {
                        "locations": ["kitchen", "living_room"],
                        "robot_position": "living_room"
                    },
                    "robot_capabilities": {
                        "navigation": True,
                        "communication": True
                    }
                },
                description="Navigation and waiting task"
            ),
            CommandTranslationExample(
                natural_language="Find my keys and bring them to me",
                expected_actions=[
                    {"action_type": "detect_object", "parameters": {"object_type": "keys", "location": "unknown"}},
                    {"action_type": "move_to", "parameters": {"target_location": "keys_location"}},
                    {"action_type": "grasp", "parameters": {"object_id": "keys"}},
                    {"action_type": "navigate", "parameters": {"target_location": "user_position"}},
                    {"action_type": "deliver", "parameters": {"object_id": "keys"}}
                ],
                context={
                    "environment": {
                        "objects": ["keys", "sofa", "table"],
                        "locations": ["sofa", "table", "user_position"]
                    },
                    "robot_capabilities": {
                        "navigation": True,
                        "manipulation": True,
                        "object_recognition": True
                    }
                },
                description="Object search and delivery task"
            )
        ]

    async def demonstrate_translation_process(self, example: CommandTranslationExample) -> Dict[str, Any]:
        """
        Demonstrate the complete translation process for an example
        """
        try:
            self.logger.info(f"Translating command: {example.natural_language}",
                           component="CommandTranslationExamples")

            # Step 1: Create a prompt for the LLM
            prompt = self.prompt_builder.build_command_planning_prompt(
                natural_command=example.natural_language,
                environment_context=example.context
            )

            self.logger.info(f"Created prompt with {len(prompt)} characters",
                           component="CommandTranslationExamples")

            # Step 2: Simulate LLM planning (in a real system, this would call the actual LLM)
            # For demonstration, we'll create action steps based on the expected actions
            action_steps = self._create_action_steps_from_example(example)

            self.logger.info(f"Generated {len(action_steps)} action steps",
                           component="CommandTranslationExamples")

            # Step 3: Generate ROS 2 action sequence
            action_sequence = self.action_generator.generate_action_sequence(
                action_steps=action_steps,
                original_command=example.natural_language,
                context=example.context
            )

            self.logger.info(f"Generated {len(action_sequence.actions)} ROS 2 actions",
                           component="CommandTranslationExamples")

            # Step 4: Validate the sequence
            validation = self.action_generator.validate_action_sequence(action_sequence)
            self.logger.info(f"Validation result: {validation['valid']}",
                           component="CommandTranslationExamples")

            # Step 5: Optimize the sequence
            optimized_sequence = self.action_generator.optimize_action_sequence(action_sequence)
            self.logger.info(f"Optimized to {len(optimized_sequence.actions)} actions",
                           component="CommandTranslationExamples")

            return {
                "success": True,
                "original_command": example.natural_language,
                "generated_actions": [action.description for action in optimized_sequence.actions],
                "action_count": len(optimized_sequence.actions),
                "validation_result": validation,
                "example_description": example.description
            }

        except Exception as e:
            self.error_handler.handle_exception(e, "CommandTranslationExamples.demonstrate_translation_process")
            return {
                "success": False,
                "error": str(e),
                "original_command": example.natural_language
            }

    def _create_action_steps_from_example(self, example: CommandTranslationExample) -> List[ActionStep]:
        """
        Create ActionStep objects from example data (in a real system, this would come from LLM)
        """
        action_steps = []
        for i, expected_action in enumerate(example.expected_actions):
            action_step = ActionStep(
                action_type=expected_action.get("action_type", "unknown"),
                parameters=expected_action.get("parameters", {}),
                description=f"Step {i+1}: {expected_action.get('action_type', 'unknown')} action"
            )
            action_steps.append(action_step)
        return action_steps

    async def run_all_examples(self) -> List[Dict[str, Any]]:
        """
        Run all command translation examples and return results
        """
        results = []

        for i, example in enumerate(self.examples):
            self.logger.info(f"Running example {i+1}: {example.description}",
                           component="CommandTranslationExamples")

            result = await self.demonstrate_translation_process(example)
            results.append(result)

        return results

    def compare_with_expected(self, generated_actions: List[str], expected_actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare generated actions with expected actions
        """
        comparison = {
            "match_count": 0,
            "total_expected": len(expected_actions),
            "total_generated": len(generated_actions),
            "matches": [],
            "mismatches": [],
            "missing": [],
            "extra": []
        }

        # For simplicity, we'll just compare action types
        expected_types = [action.get("action_type", "") for action in expected_actions]
        generated_types = [self._extract_action_type(action) for action in generated_actions]

        for i, exp_type in enumerate(expected_types):
            if i < len(generated_types) and exp_type == generated_types[i]:
                comparison["match_count"] += 1
                comparison["matches"].append({
                    "index": i,
                    "expected": exp_type,
                    "generated": generated_types[i]
                })
            else:
                comparison["mismatches"].append({
                    "index": i,
                    "expected": exp_type,
                    "generated": generated_types[i] if i < len(generated_types) else "NONE"
                })

        # Identify missing and extra actions
        if len(generated_types) > len(expected_types):
            for i in range(len(expected_types), len(generated_types)):
                comparison["extra"].append({
                    "index": i,
                    "generated": generated_types[i]
                })
        elif len(expected_types) > len(generated_types):
            for i in range(len(generated_types), len(expected_types)):
                comparison["missing"].append({
                    "index": i,
                    "expected": expected_types[i]
                })

        return comparison

    def _extract_action_type(self, action_description: str) -> str:
        """
        Extract action type from action description (simplified)
        """
        action_description_lower = action_description.lower()
        if "detect" in action_description_lower:
            return "detect_object"
        elif "move" in action_description_lower or "navigate" in action_description_lower:
            return "move_to"
        elif "grasp" in action_description_lower or "pick" in action_description_lower:
            return "grasp"
        elif "place" in action_description_lower or "put" in action_description_lower:
            return "place"
        elif "go" in action_description_lower:
            return "navigate"
        else:
            return "unknown"

    async def generate_ros2_code_example(self) -> str:
        """
        Generate example ROS 2 code that would execute a translated command
        """
        # Use the first example
        example = self.examples[0]

        # Create action steps
        action_steps = self._create_action_steps_from_example(example)

        # Generate action sequence
        action_sequence = self.action_generator.generate_action_sequence(
            action_steps=action_steps,
            original_command=example.natural_language,
            context=example.context
        )

        # Generate ROS 2 code
        ros2_code = self.action_generator.generate_ros2_execution_code(action_sequence)

        return ros2_code


async def run_command_translation_examples():
    """
    Run the command translation examples
    """
    print("Command Translation Examples for VLA System")
    print("=" * 60)

    examples = CommandTranslationExamples()

    print(f"\nLoaded {len(examples.examples)} command translation examples:")
    for i, example in enumerate(examples.examples, 1):
        print(f"  {i}. {example.description}")
        print(f"     Command: '{example.natural_language}'")

    print(f"\nRunning translation process for all examples...")

    results = await examples.run_all_examples()

    print(f"\nTranslation Results:")
    for i, result in enumerate(results, 1):
        status = "✓ SUCCESS" if result["success"] else "✗ FAILED"
        print(f"  Example {i}: {status}")
        if result["success"]:
            print(f"    Command: {result['original_command']}")
            print(f"    Actions: {result['action_count']}")
            print(f"    Generated: {result['generated_actions'][:3]}{'...' if len(result['generated_actions']) > 3 else ''}")
        else:
            print(f"    Error: {result['error']}")

    print(f"\nDemonstrating detailed process for first example:")
    detailed_result = await examples.demonstrate_translation_process(examples.examples[0])

    if detailed_result["success"]:
        print(f"  Original Command: {detailed_result['original_command']}")
        print(f"  Generated Actions ({len(detailed_result['generated_actions'])}):")
        for j, action in enumerate(detailed_result['generated_actions'], 1):
            print(f"    {j}. {action}")

        # Show comparison with expected
        comparison = examples.compare_with_expected(
            detailed_result['generated_actions'],
            examples.examples[0].expected_actions
        )
        print(f"  Comparison with expected actions:")
        print(f"    Matches: {comparison['match_count']}/{comparison['total_expected']}")
        if comparison['mismatches']:
            print(f"    Mismatches: {len(comparison['mismatches'])}")
        if comparison['missing']:
            print(f"    Missing: {len(comparison['missing'])}")
        if comparison['extra']:
            print(f"    Extra: {len(comparison['extra'])}")

    # Show example ROS 2 code generation
    print(f"\nExample ROS 2 execution code generated:")
    ros2_code = await examples.generate_ros2_code_example()
    lines = ros2_code.split('\n')
    print(f"  Lines of code: {len(lines)}")
    print(f"  First few lines:")
    for line in lines[:10]:
        print(f"    {line}")
    print(f"    ...")

    print(f"\nCommand translation examples completed successfully!")


def create_prompt_template_usage_examples():
    """
    Show examples of how to use the prompt templates
    """
    print("\nPrompt Template Usage Examples")
    print("=" * 40)

    # Show how to load and use a template
    import os
    from pathlib import Path

    # Define the template directory
    template_dir = Path("src/llm_integration/prompt_templates")

    if template_dir.exists():
        templates = list(template_dir.glob("*.txt"))
        print(f"Available templates: {len(templates)}")

        for template_file in templates:
            print(f"  - {template_file.name}")

            # Show first few lines of the template
            with open(template_file, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                print(f"    Variables: {[line.strip() for line in lines if '{' in line and '}' in line][:3]}")
    else:
        print("Template directory not found, showing example usage:")
        print("  - robotics_command_planning.txt")
        print("  - navigation_planning.txt")
        print("  - manipulation_planning.txt")
        print("  - perception_analysis.txt")
        print("  - hri_communication.txt")


if __name__ == "__main__":
    # Run the command translation examples
    asyncio.run(run_command_translation_examples())

    # Show prompt template usage
    create_prompt_template_usage_examples()