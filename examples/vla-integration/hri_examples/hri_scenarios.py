"""
Human-Robot Interaction (HRI) Scenarios for Vision-Language-Action (VLA) System

This module provides example HRI scenarios demonstrating natural interaction
between humans and robots, including error recovery and clarification handling.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class InteractionScenario(Enum):
    """Types of HRI scenarios"""
    BASIC_COMMAND = "basic_command"
    AMBIGUOUS_COMMAND = "ambiguous_command"
    TASK_WITH_ERROR = "task_with_error"
    COLLABORATIVE_TASK = "collaborative_task"
    SAFETY_INTERVENTION = "safety_intervention"
    LEARNING_INTERACTION = "learning_interaction"


@dataclass
class HRIExchange:
    """Represents a single exchange in an HRI scenario"""
    speaker: str  # "human" or "robot"
    message: str
    intent: Optional[str] = None  # The interpreted intent
    action_taken: Optional[str] = None  # Action executed by robot
    feedback: Optional[str] = None  # Additional feedback
    timestamp: Optional[float] = None


class HRIScenario:
    """Represents a complete HRI scenario"""

    def __init__(self, name: str, description: str, scenario_type: InteractionScenario):
        self.name = name
        self.description = description
        self.scenario_type = scenario_type
        self.exchanges: List[HRIExchange] = []
        self.context: Dict[str, Any] = {}
        self.success_criteria: List[str] = []
        self.failure_indicators: List[str] = []

    def add_exchange(self, speaker: str, message: str, intent: Optional[str] = None,
                    action_taken: Optional[str] = None, feedback: Optional[str] = None):
        """Add an exchange to the scenario"""
        exchange = HRIExchange(
            speaker=speaker,
            message=message,
            intent=intent,
            action_taken=action_taken,
            feedback=feedback,
            timestamp=asyncio.get_event_loop().time()
        )
        self.exchanges.append(exchange)

    def set_context(self, context: Dict[str, Any]):
        """Set the context for the scenario"""
        self.context.update(context)

    def add_success_criteria(self, criteria: List[str]):
        """Add success criteria for the scenario"""
        self.success_criteria.extend(criteria)

    def add_failure_indicators(self, indicators: List[str]):
        """Add failure indicators for the scenario"""
        self.failure_indicators.extend(indicators)

    def to_dict(self) -> Dict[str, Any]:
        """Convert scenario to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type.value,
            "context": self.context,
            "exchanges": [
                {
                    "speaker": ex.speaker,
                    "message": ex.message,
                    "intent": ex.intent,
                    "action_taken": ex.action_taken,
                    "feedback": ex.feedback,
                    "timestamp": ex.timestamp
                }
                for ex in self.exchanges
            ],
            "success_criteria": self.success_criteria,
            "failure_indicators": self.failure_indicators
        }


class HRIScenarioGenerator:
    """
    Generator for HRI scenarios demonstrating various interaction patterns
    """

    def __init__(self):
        self.scenarios: List[HRIScenario] = []
        self._generate_scenarios()

    def _generate_scenarios(self):
        """Generate example HRI scenarios"""
        self.scenarios.append(self._create_basic_command_scenario())
        self.scenarios.append(self._create_ambiguous_command_scenario())
        self.scenarios.append(self._create_task_with_error_scenario())
        self.scenarios.append(self._create_collaborative_task_scenario())
        self.scenarios.append(self._create_safety_intervention_scenario())
        self.scenarios.append(self._create_learning_interaction_scenario())

    def _create_basic_command_scenario(self) -> HRIScenario:
        """Create a basic command scenario"""
        scenario = HRIScenario(
            name="Basic Object Manipulation",
            description="Simple command to pick up and move an object",
            scenario_type=InteractionScenario.BASIC_COMMAND
        )

        scenario.set_context({
            "environment": {
                "objects": ["red_cup", "blue_book", "green_pen"],
                "locations": ["table", "shelf", "counter"]
            },
            "robot_capabilities": ["navigation", "manipulation", "object_recognition"],
            "user_goal": "Move red cup from table to shelf"
        })

        scenario.add_exchange("human", "Please pick up the red cup from the table and place it on the shelf.")
        scenario.add_exchange("robot", "I see a red cup on the table. I'll pick it up and move it to the shelf.",
                             intent="move_object", action_taken="navigation_to_table")
        scenario.add_exchange("robot", "Picking up the red cup now.",
                             intent="grasp_object", action_taken="grasping_red_cup")
        scenario.add_exchange("robot", "Moving to the shelf location.",
                             intent="navigation", action_taken="navigation_to_shelf")
        scenario.add_exchange("robot", "Placing the red cup on the shelf. Task completed!",
                             intent="placement", action_taken="placing_cup_on_shelf")

        scenario.add_success_criteria([
            "Red cup moved from table to shelf",
            "Robot successfully recognized red cup",
            "Navigation completed without obstacles",
            "Grasp and placement executed successfully"
        ])

        return scenario

    def _create_ambiguous_command_scenario(self) -> HRIScenario:
        """Create a scenario with ambiguous command requiring clarification"""
        scenario = HRIScenario(
            name="Ambiguous Reference Resolution",
            description="User gives ambiguous command requiring clarification",
            scenario_type=InteractionScenario.AMBIGUOUS_COMMAND
        )

        scenario.set_context({
            "environment": {
                "objects": ["red_cup", "blue_cup", "green_mug", "white_mug"],
                "locations": ["left_table", "right_table", "counter"]
            },
            "robot_capabilities": ["object_recognition", "communication"],
            "user_goal": "Move the cup from the left table to the right table"
        })

        scenario.add_exchange("human", "Move the cup from the left table to the right table.")
        scenario.add_exchange("robot", "I see multiple cups on the left table: a red cup and a blue cup. Which one did you want me to move?",
                             intent="request_clarification", feedback="ambiguity_detected")
        scenario.add_exchange("human", "The red one.")
        scenario.add_exchange("robot", "Got it. Moving the red cup from the left table to the right table.",
                             intent="move_object", action_taken="navigation_to_left_table")
        scenario.add_exchange("robot", "Picking up the red cup.",
                             intent="grasp_object", action_taken="grasping_red_cup")
        scenario.add_exchange("robot", "Moving to the right table.",
                             intent="navigation", action_taken="navigation_to_right_table")
        scenario.add_exchange("robot", "Placing the red cup on the right table. Task completed!",
                             intent="placement", action_taken="placing_cup_on_right_table")

        scenario.add_success_criteria([
            "Correct cup (red) identified and moved",
            "Appropriate clarification requested",
            "User provided clear specification",
            "Task completed successfully"
        ])
        scenario.add_failure_indicators([
            "Robot guessed incorrectly without clarification",
            "User had to repeat the same information multiple times",
            "Wrong object moved"
        ])

        return scenario

    def _create_task_with_error_scenario(self) -> HRIScenario:
        """Create a scenario where a task encounters an error and requires recovery"""
        scenario = HRIScenario(
            name="Error Recovery and Alternative Solutions",
            description="Task fails and robot suggests alternatives",
            scenario_type=InteractionScenario.TASK_WITH_ERROR
        )

        scenario.set_context({
            "environment": {
                "objects": ["heavy_box", "light_box", "book"],
                "locations": ["floor", "table", "shelf"],
                "obstacles": ["chair_in_path"]
            },
            "robot_capabilities": ["navigation", "manipulation", "communication"],
            "user_goal": "Move the heavy box to the shelf"
        })

        scenario.add_exchange("human", "Please move the heavy box to the shelf.")
        scenario.add_exchange("robot", "I'll move the heavy box to the shelf. Navigating there now.",
                             intent="navigation", action_taken="navigation_to_heavy_box")
        scenario.add_exchange("robot", "Attempting to grasp the heavy box.",
                             intent="grasp_object", action_taken="grasping_heavy_box")
        scenario.add_exchange("robot", "I'm sorry, but the box is too heavy for me to lift. It weighs approximately 10kg, but I can only handle objects up to 5kg. I could move the light box instead, or I could help you move it together. What would you prefer?",
                             intent="error_recovery", feedback="weight_exceeded_limit")
        scenario.add_exchange("human", "Okay, move the light box to the shelf instead.")
        scenario.add_exchange("robot", "I'll move the light box to the shelf instead.",
                             intent="alternative_task", action_taken="navigation_to_light_box")
        scenario.add_exchange("robot", "Picking up the light box.",
                             intent="grasp_object", action_taken="grasping_light_box")
        scenario.add_exchange("robot", "Moving to the shelf and placing the light box. Task completed!",
                             intent="placement", action_taken="placing_light_box_on_shelf")

        scenario.add_success_criteria([
            "Robot correctly identified weight limitation",
            "Appropriate alternative suggested",
            "User accepted alternative solution",
            "Alternative task completed successfully"
        ])
        scenario.add_failure_indicators([
            "Robot attempted to lift object beyond capacity",
            "No alternative offered after failure",
            "User had to provide multiple alternative solutions"
        ])

        return scenario

    def _create_collaborative_task_scenario(self) -> HRIScenario:
        """Create a scenario involving human-robot collaboration"""
        scenario = HRIScenario(
            name="Collaborative Table Clearing",
            description="Human and robot work together to clear a table",
            scenario_type=InteractionScenario.COLLABORATIVE_TASK
        )

        scenario.set_context({
            "environment": {
                "objects": ["plates", "cups", "utensils", "napkins", "food_items"],
                "locations": ["table", "kitchen_counter", "dishwasher", "trash_bin"],
                "workspace": "dining_table"
            },
            "robot_capabilities": ["navigation", "manipulation", "communication", "object_categorization"],
            "user_goal": "Clear the dining table after dinner"
        })

        scenario.add_exchange("human", "Let's clear this table together.")
        scenario.add_exchange("robot", "Great! I can handle the plates and cups, while you handle the food items and utensils. I'll start by collecting the plates.",
                             intent="task_coordination", action_taken="object_classification")
        scenario.add_exchange("human", "Sounds good. I'll take the food scraps and utensils.")
        scenario.add_exchange("robot", "I see 3 plates on the table. I'll collect them and place them by the dishwasher.",
                             intent="navigation", action_taken="navigation_to_plates")
        scenario.add_exchange("robot", "Collecting the plates now.",
                             intent="grasp_object", action_taken="grasping_plate_1")
        scenario.add_exchange("robot", "I've placed the plates by the dishwasher. I'll get the cups next.",
                             intent="placement", action_taken="placing_plates_by_dishwasher")
        scenario.add_exchange("robot", "The table looks much clearer now. Is there anything else you'd like me to help with?",
                             intent="task_completion", feedback="collaboration_successful")

        scenario.add_success_criteria([
            "Task divided appropriately between human and robot",
            "Both parties understood their roles",
            "Work proceeded efficiently without interference",
            "Clear communication throughout collaboration"
        ])
        scenario.add_failure_indicators([
            "Robot and human interfered with each other's work",
            "Unclear division of labor led to confusion",
            "Lack of coordination caused inefficiency"
        ])

        return scenario

    def _create_safety_intervention_scenario(self) -> HRIScenario:
        """Create a scenario where robot intervenes for safety reasons"""
        scenario = HRIScenario(
            name="Safety Intervention and Prevention",
            description="Robot detects safety hazard and intervenes appropriately",
            scenario_type=InteractionScenario.SAFETY_INTERVENTION
        )

        scenario.set_context({
            "environment": {
                "objects": ["sharp_knife", "glass", "food_items"],
                "locations": ["counter", "sink", "cutting_board"],
                "people_present": ["user", "child"],
                "safety_concerns": ["child_near_knife", "slippery_floor"]
            },
            "robot_capabilities": ["safety_monitoring", "navigation", "manipulation", "communication"],
            "user_goal": "Prepare vegetables for cooking"
        })

        scenario.add_exchange("human", "I need to chop these vegetables. Hand me the knife.")
        scenario.add_exchange("robot", "I notice a child is nearby and there's a sharp knife on the counter. For safety, I recommend waiting until the child moves away or using a safer location for cutting.",
                             intent="safety_alert", feedback="safety_hazard_detected")
        scenario.add_exchange("human", "Oh, I didn't notice the child. Let me move them away first.")
        scenario.add_exchange("robot", "Thank you for addressing the safety concern. I'll wait until the area is clear before proceeding with any tool handling.",
                             intent="safety_wait", action_taken="monitoring_environment")
        scenario.add_exchange("human", "OK, the child is in another room now. Can you hand me the knife?")
        scenario.add_exchange("robot", "The area is clear now. Here's the knife for vegetable preparation.",
                             intent="tool_delivery", action_taken="grasping_and_delivering_knife")
        scenario.add_exchange("robot", "I'll remain nearby to monitor the situation if needed.",
                             intent="safety_monitoring", action_taken="positioning_for_monitoring")

        scenario.add_success_criteria([
            "Robot detected safety hazard proactively",
            "Appropriate safety advice provided",
            "User acknowledged and addressed safety concern",
            "Task continued safely after hazard resolved"
        ])
        scenario.add_failure_indicators([
            "Robot failed to detect safety hazard",
            "Safety intervention was too late",
            "User ignored safety advice",
            "Task proceeded despite safety concerns"
        ])

        return scenario

    def _create_learning_interaction_scenario(self) -> HRIScenario:
        """Create a scenario where robot learns from user feedback"""
        scenario = HRIScenario(
            name="Learning from User Corrections",
            description="Robot learns to improve based on user feedback",
            scenario_type=InteractionScenario.LEARNING_INTERACTION
        )

        scenario.set_context({
            "environment": {
                "objects": ["red_book", "blue_book", "green_book", "black_book"],
                "locations": ["shelf_A", "shelf_B", "shelf_C"],
                "robot_experience": ["limited_book_handling"]
            },
            "robot_capabilities": ["object_recognition", "manipulation", "learning"],
            "user_goal": "Organize books by color on shelves"
        })

        scenario.add_exchange("human", "Please put the red book on shelf A, the blue book on shelf B, and the green book on shelf C.")
        scenario.add_exchange("robot", "I'll organize the books by color on the shelves.",
                             intent="navigation", action_taken="navigation_to_books")
        scenario.add_exchange("robot", "Picking up what I believe is the red book.",
                             intent="grasp_object", action_taken="grasping_book_1")
        scenario.add_exchange("human", "Wait, that's actually the black book. The red one is to the left of it.")
        scenario.add_exchange("robot", "My apologies, I misidentified the book. Let me correct that.",
                             intent="error_acknowledgment", feedback="recognition_error_detected")
        scenario.add_exchange("robot", "You're right, that was the black book. I'll place it back and get the red book instead.",
                             intent="correction", action_taken="returning_black_book")
        scenario.add_exchange("robot", "Now I see the red book to the left as you said. Picking it up.",
                             intent="correction", action_taken="grasping_red_book")
        scenario.add_exchange("robot", "Placing the red book on shelf A as requested. Thank you for correcting me. I'll remember the color distinction for next time.",
                             intent="placement", action_taken="placing_red_book_on_shelf_A", feedback="learning_from_feedback")

        scenario.add_success_criteria([
            "Robot acknowledged and corrected its mistake",
            "User provided clear corrective feedback",
            "Robot expressed intention to learn from the error",
            "Task completed correctly after correction"
        ])
        scenario.add_failure_indicators([
            "Robot didn't acknowledge the error",
            "Robot repeated the same mistake",
            "User had to provide multiple corrections for the same error",
            "Robot didn't express learning from the feedback"
        ])

        return scenario

    def get_scenario_by_type(self, scenario_type: InteractionScenario) -> List[HRIScenario]:
        """Get scenarios of a specific type"""
        return [s for s in self.scenarios if s.scenario_type == scenario_type]

    def get_scenario_by_name(self, name: str) -> Optional[HRIScenario]:
        """Get a scenario by its name"""
        for scenario in self.scenarios:
            if scenario.name == name:
                return scenario
        return None

    def export_scenarios(self) -> Dict[str, Any]:
        """Export all scenarios in a serializable format"""
        return {
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "total_scenarios": len(self.scenarios),
            "scenario_types": list(set(s.scenario_type.value for s in self.scenarios))
        }

    def run_scenario_simulation(self, scenario_name: str) -> Dict[str, Any]:
        """
        Simulate running a scenario to demonstrate the interaction flow
        """
        scenario = self.get_scenario_by_name(scenario_name)
        if not scenario:
            return {"error": f"Scenario '{scenario_name}' not found"}

        print(f"\n--- Running HRI Scenario: {scenario.name} ---")
        print(f"Description: {scenario.description}")
        print(f"Type: {scenario.scenario_type.value}")
        print("\nContext:")
        for key, value in scenario.context.items():
            print(f"  {key}: {value}")

        print("\nInteraction Flow:")
        for i, exchange in enumerate(scenario.exchanges, 1):
            speaker_symbol = "👤" if exchange.speaker == "human" else "🤖"
            print(f"{i:2d}. {speaker_symbol} {exchange.speaker.title()}: {exchange.message}")
            if exchange.action_taken:
                print(f"     [Action: {exchange.action_taken}]")
            if exchange.intent:
                print(f"     [Intent: {exchange.intent}]")
            if exchange.feedback:
                print(f"     [Feedback: {exchange.feedback}]")

        print(f"\nSuccess Criteria:")
        for criterion in scenario.success_criteria:
            print(f"  ✓ {criterion}")

        if scenario.failure_indicators:
            print(f"\nFailure Indicators:")
            for indicator in scenario.failure_indicators:
                print(f"  ⚠ {indicator}")

        return {
            "scenario_name": scenario.name,
            "scenario_type": scenario.scenario_type.value,
            "exchanges_count": len(scenario.exchanges),
            "context_provided": bool(scenario.context),
            "success_criteria_count": len(scenario.success_criteria),
            "failure_indicators_count": len(scenario.failure_indicators)
        }


async def demonstrate_hri_scenarios():
    """
    Demonstrate the HRI scenarios and their implementation
    """
    print("Human-Robot Interaction (HRI) Scenarios for VLA System")
    print("=" * 60)

    generator = HRIScenarioGenerator()

    print(f"\nAvailable HRI Scenarios: {len(generator.scenarios)}")
    for i, scenario in enumerate(generator.scenarios, 1):
        print(f"{i:2d}. {scenario.name}")
        print(f"    Type: {scenario.scenario_type.value}")
        print(f"    Description: {scenario.description}")

    print(f"\nDetailed Simulation of Each Scenario:")

    # Run each scenario simulation
    for scenario in generator.scenarios:
        result = generator.run_scenario_simulation(scenario.name)
        print(f"\nSimulation Result: {result['exchanges_count']} exchanges processed")

    # Show scenario statistics
    print(f"\nScenario Statistics:")
    stats = generator.export_scenarios()
    print(f"  Total scenarios: {stats['total_scenarios']}")
    print(f"  Scenario types: {', '.join(stats['scenario_types'])}")

    # Group scenarios by type
    print(f"\nScenarios by Type:")
    for scenario_type in InteractionScenario:
        type_scenarios = generator.get_scenario_by_type(scenario_type)
        print(f"  {scenario_type.value}: {len(type_scenarios)} scenarios")
        for scenario in type_scenarios:
            print(f"    - {scenario.name}")

    print(f"\nHRI scenario demonstration completed!")
    print(f"\nThe scenarios demonstrate key aspects of human-robot interaction:")
    print(f"- Natural language communication")
    print(f"- Error handling and recovery")
    print(f"- Safety considerations")
    print(f"- Collaborative task execution")
    print(f"- Learning from user feedback")
    print(f"- Context-aware interaction")


def explain_hri_design_principles():
    """
    Explain the HRI design principles demonstrated in the scenarios
    """
    print("\nHRI Design Principles Demonstrated")
    print("=" * 40)

    principles = {
        "Natural Communication": {
            "description": "Interactions feel intuitive and conversational",
            "examples": [
                "Allowing natural language commands without rigid syntax",
                "Requesting clarification when commands are ambiguous",
                "Providing appropriate feedback during task execution"
            ]
        },
        "Transparency": {
            "description": "System clearly communicates its state and intentions",
            "examples": [
                "Explaining what the robot is doing and why",
                "Acknowledging mistakes and limitations",
                "Providing progress updates during tasks"
            ]
        },
        "Safety First": {
            "description": "Prioritize safety in all interactions",
            "examples": [
                "Detecting and responding to safety hazards",
                "Respecting physical and operational limits",
                "Stopping operations when safety is compromised"
            ]
        },
        "Error Recovery": {
            "description": "Handle failures gracefully and recover appropriately",
            "examples": [
                "Suggesting alternatives when tasks fail",
                "Asking for clarification when confused",
                "Learning from mistakes to improve"
            ]
        },
        "Collaboration": {
            "description": "Work effectively with humans as partners",
            "examples": [
                "Dividing tasks appropriately between human and robot",
                "Coordinating actions to avoid interference",
                "Adapting to human preferences and pace"
            ]
        }
    }

    for principle, info in principles.items():
        print(f"\n{principle}:")
        print(f"  {info['description']}")
        print(f"  Examples:")
        for example in info['examples']:
            print(f"    • {example}")


if __name__ == "__main__":
    # Run the HRI scenario demonstration
    asyncio.run(demonstrate_hri_scenarios())

    # Explain the design principles
    explain_hri_design_principles()