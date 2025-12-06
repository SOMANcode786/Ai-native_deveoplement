"""
Conversational Flow Manager for Human-Robot Interaction (HRI) in VLA System

This module manages conversational flows between humans and robots,
enabling natural and intuitive interaction with error recovery capabilities.
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re


class ConversationState(Enum):
    """Current state of the conversation"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    ERROR_RECOVERY = "error_recovery"
    TASK_EXECUTION = "task_execution"
    WAITING_FOR_INPUT = "waiting_for_input"


class InteractionType(Enum):
    """Types of interactions"""
    COMMAND = "command"
    QUESTION = "question"
    CONFIRMATION = "confirmation"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    STATUS_REQUEST = "status_request"
    CHAT = "chat"


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation"""
    turn_id: str
    user_input: str
    robot_response: str
    interaction_type: InteractionType
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    task_status: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ConversationContext:
    """Maintains context across conversation turns"""
    current_task: Optional[str] = None
    task_parameters: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    robot_state: Dict[str, Any] = field(default_factory=dict)
    environment_state: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    last_intent: Optional[str] = None
    last_confidence: float = 1.0
    waiting_for_confirmation: bool = False
    pending_action: Optional[str] = None


class ConversationalFlowManager:
    """
    Manages conversational flows for natural human-robot interaction
    Handles context, state management, and error recovery
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_context = ConversationContext()
        self.state = ConversationState.IDLE
        self.response_handlers: Dict[str, Callable] = {}
        self.intent_handlers: Dict[str, Callable] = {}
        self.confirmation_callbacks: Dict[str, Callable] = {}
        self.conversation_history: List[ConversationTurn] = []
        self.max_history_length = 20

        # Initialize default handlers
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """Set up default response and intent handlers"""
        # Default intent handlers
        self.intent_handlers['command'] = self._handle_command_intent
        self.intent_handlers['question'] = self._handle_question_intent
        self.intent_handlers['status'] = self._handle_status_intent
        self.intent_handlers['greeting'] = self._handle_greeting_intent

        # Default response handlers
        self.response_handlers['confirmation'] = self._handle_confirmation_response
        self.response_handlers['correction'] = self._handle_correction_response

    async def process_user_input(self, user_input: str) -> str:
        """
        Process user input and generate appropriate robot response

        Args:
            user_input: Natural language input from user

        Returns:
            Robot response as natural language
        """
        try:
            self.logger.info(f"Processing user input: {user_input}", extra={
                'user_input': user_input,
                'state': self.state.value
            })

            # Update state to processing
            self.state = ConversationState.PROCESSING

            # Determine interaction type
            interaction_type = self._classify_interaction_type(user_input)

            # Process based on current state and interaction type
            if self.state == ConversationState.WAITING_FOR_CONFIRMATION:
                response = await self._handle_confirmation_input(user_input)
            elif self.current_context.waiting_for_confirmation:
                response = await self._handle_confirmation_input(user_input)
            else:
                response = await self._process_interaction(user_input, interaction_type)

            # Create conversation turn record
            turn = ConversationTurn(
                turn_id=f"turn_{len(self.conversation_history) + 1}",
                user_input=user_input,
                robot_response=response,
                interaction_type=interaction_type,
                timestamp=datetime.now(),
                context=self._get_context_snapshot()
            )

            # Add to history
            self.conversation_history.append(turn)
            self.current_context.conversation_history.append(turn)

            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length:
                self.conversation_history = self.conversation_history[-self.max_history_length:]
            if len(self.current_context.conversation_history) > self.max_history_length:
                self.current_context.conversation_history = self.current_context.conversation_history[-self.max_history_length:]

            self.logger.info(f"Generated response: {response[:50]}...", extra={
                'response_length': len(response)
            })

            # Update state to responding
            self.state = ConversationState.RESPONDING

            return response

        except Exception as e:
            self.logger.error(f"Error processing user input: {e}")
            return await self._handle_error_recovery(user_input, str(e))

    def _classify_interaction_type(self, user_input: str) -> InteractionType:
        """Classify the type of interaction based on user input"""
        user_lower = user_input.lower().strip()

        # Check for commands (imperative sentences)
        command_indicators = ['please', 'can you', 'could you', 'move', 'go', 'pick', 'place', 'clean', 'bring']
        if any(indicator in user_lower for indicator in command_indicators):
            return InteractionType.COMMAND

        # Check for questions (interrogative sentences)
        question_indicators = ['?', 'what', 'where', 'when', 'how', 'why', 'who', 'can', 'do', 'is', 'are', 'will']
        if any(indicator in user_lower for indicator in question_indicators) or user_lower.endswith('?'):
            return InteractionType.QUESTION

        # Check for confirmations
        confirmation_indicators = ['yes', 'no', 'yep', 'nope', 'sure', 'ok', 'okay', 'alright']
        if any(indicator in user_lower for indicator in confirmation_indicators):
            return InteractionType.CONFIRMATION

        # Check for corrections
        correction_indicators = ['no,', 'not', 'actually', 'wait', 'correction', 'change']
        if any(indicator in user_lower for indicator in correction_indicators):
            return InteractionType.CORRECTION

        # Check for clarifications
        clarification_indicators = ['what do you mean', 'explain', 'clarify', 'repeat', 'again']
        if any(indicator in user_lower for indicator in clarification_indicators):
            return InteractionType.CLARIFICATION

        # Default to command if it looks like an instruction
        if self._looks_like_command(user_input):
            return InteractionType.COMMAND

        # Default to chat
        return InteractionType.CHAT

    def _looks_like_command(self, text: str) -> bool:
        """Determine if text looks like a command"""
        # Check for imperative verbs at the beginning
        imperative_verbs = ['move', 'go', 'pick', 'place', 'take', 'bring', 'clean', 'organize', 'help']
        first_word = text.split()[0].lower() if text.split() else ''
        return first_word in imperative_verbs

    async def _process_interaction(self, user_input: str, interaction_type: InteractionType) -> str:
        """Process interaction based on type"""
        # Determine intent
        intent = await self._determine_intent(user_input, interaction_type)

        # Store last intent and confidence
        self.current_context.last_intent = intent
        self.current_context.last_confidence = 0.9  # Default confidence

        # Process based on intent
        if intent in self.intent_handlers:
            return await self.intent_handlers[intent](user_input)
        else:
            return await self._handle_unknown_intent(user_input)

    async def _determine_intent(self, user_input: str, interaction_type: InteractionType) -> str:
        """Determine the intent behind user input"""
        user_lower = user_input.lower()

        # Intent classification rules
        if interaction_type == InteractionType.QUESTION:
            if any(word in user_lower for word in ['where', 'location', 'position', 'find']):
                return 'location_inquiry'
            elif any(word in user_lower for word in ['status', 'progress', 'done', 'complete']):
                return 'status_inquiry'
            elif any(word in user_lower for word in ['can you', 'able', 'possible']):
                return 'capability_inquiry'
            else:
                return 'question'
        elif interaction_type == InteractionType.COMMAND:
            if any(word in user_lower for word in ['move', 'go to', 'navigate', 'travel']):
                return 'navigation'
            elif any(word in user_lower for word in ['pick', 'grasp', 'take', 'lift', 'hold']):
                return 'manipulation'
            elif any(word in user_lower for word in ['place', 'put', 'set', 'drop', 'release']):
                return 'placement'
            elif any(word in user_lower for word in ['clean', 'organize', 'arrange']):
                return 'cleanup'
            else:
                return 'command'
        elif any(greeting in user_lower for greeting in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return 'greeting'
        else:
            return 'unknown'

    async def _handle_command_intent(self, user_input: str) -> str:
        """Handle command intent"""
        # Extract task and parameters
        task, parameters = await self._extract_task_and_parameters(user_input)

        # Store task information
        self.current_context.current_task = task
        self.current_context.task_parameters.update(parameters)

        # Check if we need confirmation
        if self._requires_confirmation(task, parameters):
            self.current_context.waiting_for_confirmation = True
            self.current_context.pending_action = task

            confirmation_text = self._generate_confirmation_text(task, parameters)
            return f"Did you mean for me to {confirmation_text}? Please confirm."

        # Execute task directly if no confirmation needed
        response = await self._execute_task(task, parameters)
        return response

    async def _handle_question_intent(self, user_input: str) -> str:
        """Handle question intent"""
        # This would typically connect to a question-answering system
        # For now, we'll provide some basic responses
        user_lower = user_input.lower()

        if 'where' in user_lower and ('robot' in user_lower or 'you' in user_lower):
            return f"I am currently at position {self.current_context.robot_state.get('position', 'unknown')}."
        elif 'status' in user_lower or 'doing' in user_lower:
            current_task = self.current_context.current_task
            if current_task:
                return f"I am currently working on: {current_task}."
            else:
                return "I am ready to help. What would you like me to do?"
        else:
            return "I can help with various tasks like moving objects, navigating, or answering questions about my status. What would you like to know?"

    async def _handle_status_intent(self, user_input: str) -> str:
        """Handle status request intent"""
        return f"I am currently {self.state.value}. My last task was: {self.current_context.current_task or 'none'}. I'm ready to assist you."

    async def _handle_greeting_intent(self, user_input: str) -> str:
        """Handle greeting intent"""
        return "Hello! I'm your robotic assistant. How can I help you today?"

    async def _handle_confirmation_input(self, user_input: str) -> str:
        """Handle user response to confirmation request"""
        user_lower = user_input.lower().strip()

        if any(word in user_lower for word in ['yes', 'yep', 'sure', 'ok', 'okay', 'alright', 'confirm']):
            # Execute the pending action
            task = self.current_context.pending_action
            if task:
                response = await self._execute_task(task, self.current_context.task_parameters)
                self.current_context.waiting_for_confirmation = False
                self.current_context.pending_action = None
                return response
            else:
                self.current_context.waiting_for_confirmation = False
                return "I don't have a pending action to confirm. How else can I help?"
        elif any(word in user_lower for word in ['no', 'nope', 'cancel', 'stop', 'never mind']):
            # Cancel the pending action
            self.current_context.waiting_for_confirmation = False
            self.current_context.pending_action = None
            return "Action cancelled. How else can I help?"
        else:
            # Unclear response, ask for clarification
            pending_action = self.current_context.pending_action
            confirmation_text = self._generate_confirmation_text(pending_action, self.current_context.task_parameters) if pending_action else "the requested action"
            return f"I didn't understand your response. Did you mean to confirm or cancel {confirmation_text}? Please say yes or no."

    async def _handle_error_recovery(self, user_input: str, error_message: str) -> str:
        """Handle error recovery in conversation"""
        self.state = ConversationState.ERROR_RECOVERY
        self.logger.error(f"Error in conversation: {error_message}")

        # Try to recover gracefully
        if self.current_context.current_task:
            return f"I encountered an error while processing your request: {error_message}. Would you like me to try again or help with something else?"
        else:
            return f"I encountered an error: {error_message}. How else can I help you?"

    def _requires_confirmation(self, task: str, parameters: Dict[str, Any]) -> bool:
        """Determine if a task requires confirmation"""
        # Tasks that typically require confirmation
        confirmation_tasks = ['navigation', 'manipulation', 'placement']

        # Check if task is in the list
        if any(ct in task.lower() for ct in confirmation_tasks):
            return True

        # Check for specific parameters that require confirmation
        if 'person' in str(parameters).lower() or 'fragile' in str(parameters).lower():
            return True

        return False

    def _generate_confirmation_text(self, task: str, parameters: Dict[str, Any]) -> str:
        """Generate text for confirmation request"""
        if task == 'navigation':
            target = parameters.get('target_location', 'the specified location')
            return f"navigate to {target}"
        elif task == 'manipulation':
            object_desc = parameters.get('object_description', 'the object')
            return f"pick up {object_desc}"
        elif task == 'placement':
            object_desc = parameters.get('object_description', 'the object')
            target = parameters.get('target_location', 'the location')
            return f"place {object_desc} at {target}"
        else:
            return f"perform {task} with parameters {parameters}"

    async def _extract_task_and_parameters(self, user_input: str) -> tuple:
        """Extract task and parameters from user input"""
        # This is a simplified extraction - in practice, you'd use NLP techniques
        user_lower = user_input.lower()

        # Determine task based on keywords
        if any(word in user_lower for word in ['move', 'go', 'navigate', 'travel']):
            task = 'navigation'
        elif any(word in user_lower for word in ['pick', 'grasp', 'take', 'lift', 'hold']):
            task = 'manipulation'
        elif any(word in user_lower for word in ['place', 'put', 'set', 'drop', 'release']):
            task = 'placement'
        elif any(word in user_lower for word in ['clean', 'organize', 'arrange']):
            task = 'cleanup'
        else:
            task = 'command'

        # Extract parameters (simplified)
        parameters = {}

        # Extract location information
        location_patterns = [
            r'to (\w+)',
            r'at (\w+)',
            r'in the (\w+)',
            r'(\w+) room',
            r'(\w+) area'
        ]

        for pattern in location_patterns:
            match = re.search(pattern, user_lower)
            if match:
                parameters['target_location'] = match.group(1)
                break

        # Extract object information
        object_patterns = [
            r'(\w+ \w+)',  # color object, e.g., "red cup"
            r'the (\w+)',  # "the cup"
            r'a (\w+)',    # "a cup"
        ]

        for pattern in object_patterns:
            match = re.search(pattern, user_lower)
            if match:
                obj_desc = match.group(1)
                if 'object_description' not in parameters:
                    parameters['object_description'] = obj_desc
                break

        return task, parameters

    async def _execute_task(self, task: str, parameters: Dict[str, Any]) -> str:
        """Execute a task (simulated for this example)"""
        # In a real implementation, this would connect to the VLA system
        # to execute the task and return the result

        if task == 'navigation':
            location = parameters.get('target_location', 'the destination')
            return f"Okay, I'm navigating to {location}."
        elif task == 'manipulation':
            obj_desc = parameters.get('object_description', 'the object')
            return f"Okay, I'm going to pick up {obj_desc}."
        elif task == 'placement':
            obj_desc = parameters.get('object_description', 'the object')
            location = parameters.get('target_location', 'the location')
            return f"Okay, I'm going to place {obj_desc} at {location}."
        else:
            return f"Okay, I'm going to {task}."

    def _get_context_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the current context"""
        return {
            'current_task': self.current_context.current_task,
            'last_intent': self.current_context.last_intent,
            'waiting_for_confirmation': self.current_context.waiting_for_confirmation,
            'robot_state': self.current_context.robot_state,
            'environment_state': self.current_context.environment_state
        }

    async def _handle_unknown_intent(self, user_input: str) -> str:
        """Handle unknown intent"""
        return f"I'm not sure I understood. Could you rephrase that? I can help with tasks like moving objects, navigating, or answering questions."

    def update_robot_state(self, new_state: Dict[str, Any]):
        """Update the robot's state in the conversation context"""
        self.current_context.robot_state.update(new_state)
        self.logger.info("Robot state updated", extra={'robot_state': new_state})

    def update_environment_state(self, new_state: Dict[str, Any]):
        """Update the environment state in the conversation context"""
        self.current_context.environment_state.update(new_state)
        self.logger.info("Environment state updated", extra={'environment_state': new_state})

    def get_conversation_context(self) -> ConversationContext:
        """Get the current conversation context"""
        return self.current_context

    def reset_conversation(self):
        """Reset the conversation to initial state"""
        self.current_context = ConversationContext()
        self.state = ConversationState.IDLE
        self.conversation_history = []
        self.logger.info("Conversation reset to initial state")

    async def request_clarification(self, question: str) -> str:
        """
        Request clarification from the user

        Args:
            question: The clarification question to ask the user

        Returns:
            User's response to the clarification question
        """
        self.state = ConversationState.WAITING_FOR_INPUT
        # In a real implementation, this would wait for user input
        # For this example, we'll return a placeholder
        return f"CLARIFICATION_REQUEST: {question}"

    def register_intent_handler(self, intent: str, handler: Callable):
        """Register a custom intent handler"""
        self.intent_handlers[intent] = handler
        self.logger.info(f"Registered intent handler for: {intent}")

    def register_response_handler(self, response_type: str, handler: Callable):
        """Register a custom response handler"""
        self.response_handlers[response_type] = handler
        self.logger.info(f"Registered response handler for: {response_type}")


class HRIContextManager:
    """Manages high-level HRI context and preferences"""

    def __init__(self, flow_manager: ConversationalFlowManager):
        self.flow_manager = flow_manager
        self.logger = logging.getLogger(__name__)

    def set_user_preference(self, preference_key: str, preference_value: Any):
        """Set a user preference in the conversation context"""
        self.flow_manager.current_context.user_preferences[preference_key] = preference_value
        self.logger.info(f"Set user preference: {preference_key} = {preference_value}")

    def get_user_preference(self, preference_key: str, default_value: Any = None) -> Any:
        """Get a user preference from the conversation context"""
        return self.flow_manager.current_context.user_preferences.get(preference_key, default_value)

    def set_task_context(self, task_info: Dict[str, Any]):
        """Set context information for the current task"""
        self.flow_manager.current_context.task_parameters.update(task_info)
        self.logger.info(f"Updated task context: {task_info}")

    def get_recent_interactions(self, count: int = 5) -> List[ConversationTurn]:
        """Get recent conversation turns"""
        return self.flow_manager.conversation_history[-count:]


# Example usage and testing
async def test_conversational_flow():
    """Test the conversational flow manager"""
    print("Testing Conversational Flow Manager")
    print("=" * 40)

    # Create flow manager
    flow_manager = ConversationalFlowManager()
    context_manager = HRIContextManager(flow_manager)

    # Test conversations
    test_inputs = [
        "Hello robot",
        "Please move to the kitchen",
        "yes",  # Confirmation
        "Where are you now?",
        "Can you pick up the red cup?",
        "no",  # Deny confirmation
        "How are you doing?",
        "Take the blue pen to the desk",
    ]

    print("\nSimulating conversation:")
    for i, user_input in enumerate(test_inputs, 1):
        print(f"\n{i}. User: {user_input}")
        response = await flow_manager.process_user_input(user_input)
        print(f"   Robot: {response}")

        # Update mock states for demonstration
        if "move" in user_input.lower() or "navigate" in user_input.lower():
            flow_manager.update_robot_state({"position": "moving_to_kitchen", "battery": 85})
        elif "pick" in user_input.lower() or "grasp" in user_input.lower():
            flow_manager.update_robot_state({"position": "at_object", "gripper": "closed"})

    # Show conversation context
    print(f"\nConversation Context:")
    context = flow_manager.get_conversation_context()
    print(f"  Current task: {context.current_task}")
    print(f"  Last intent: {context.last_intent}")
    print(f"  Waiting for confirmation: {context.waiting_for_confirmation}")
    print(f"  Total turns: {len(flow_manager.conversation_history)}")

    # Show recent interactions
    print(f"\nRecent Interactions:")
    recent = context_manager.get_recent_interactions(3)
    for turn in recent:
        print(f"  {turn.interaction_type.value}: {turn.user_input[:30]}... -> {turn.robot_response[:30]}...")

    print(f"\nConversational flow manager test completed!")


if __name__ == "__main__":
    asyncio.run(test_conversational_flow())