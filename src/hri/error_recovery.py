"""
Error Recovery Mechanisms for Human-Robot Interaction (HRI) in VLA System

This module provides comprehensive error recovery capabilities for handling
ambiguous commands, execution failures, and other error conditions in the HRI system.
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import random


class ErrorType(Enum):
    """Types of errors that can occur in HRI"""
    AMBIGUOUS_COMMAND = "ambiguous_command"
    EXECUTION_FAILURE = "execution_failure"
    PERCEPTION_ERROR = "perception_error"
    COMMUNICATION_ERROR = "communication_error"
    SAFETY_VIOLATION = "safety_violation"
    CAPABILITY_EXCEEDED = "capability_exceeded"
    TEMPORAL_CONSTRAINT = "temporal_constraint"
    RESOURCE_UNAVAILABLE = "resource_unavailable"


class RecoveryStrategy(Enum):
    """Strategies for error recovery"""
    REQUEST_CLARIFICATION = "request_clarification"
    SUGGEST_ALTERNATIVE = "suggest_alternative"
    DELEGATE_TO_USER = "delegate_to_user"
    SIMPLIFY_TASK = "simplify_task"
    RETRY_ACTION = "retry_action"
    ESCALATE_TO_OPERATOR = "escalate_to_operator"
    SAFE_INTERRUPT = "safe_interrupt"
    TASK_SUBSTITUTION = "task_substitution"


@dataclass
class ErrorRecoveryContext:
    """Context for error recovery"""
    error_type: ErrorType
    error_message: str
    original_command: str
    robot_state: Dict[str, Any]
    environment_state: Dict[str, Any]
    attempt_count: int = 1
    recovery_strategies_tried: List[RecoveryStrategy] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.recovery_strategies_tried is None:
            self.recovery_strategies_tried = []
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class RecoveryAction:
    """Action to take for error recovery"""
    strategy: RecoveryStrategy
    description: str
    confidence: float
    parameters: Optional[Dict[str, Any]] = None


class ErrorRecoveryManager:
    """
    Manages error recovery for the HRI system
    Handles various error types and recovery strategies
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.recovery_strategies: Dict[ErrorType, List[RecoveryStrategy]] = self._initialize_strategies()
        self.recovery_handlers: Dict[RecoveryStrategy, Callable] = self._initialize_handlers()
        self.max_retry_attempts = 3
        self.recovery_history: List[ErrorRecoveryContext] = []
        self.max_history_length = 50

    def _initialize_strategies(self) -> Dict[ErrorType, List[RecoveryStrategy]]:
        """Initialize default recovery strategies for each error type"""
        return {
            ErrorType.AMBIGUOUS_COMMAND: [
                RecoveryStrategy.REQUEST_CLARIFICATION,
                RecoveryStrategy.SUGGEST_ALTERNATIVE,
                RecoveryStrategy.DELEGATE_TO_USER
            ],
            ErrorType.EXECUTION_FAILURE: [
                RecoveryStrategy.RETRY_ACTION,
                RecoveryStrategy.SIMPLIFY_TASK,
                RecoveryStrategy.SUGGEST_ALTERNATIVE
            ],
            ErrorType.PERCEPTION_ERROR: [
                RecoveryStrategy.RETRY_ACTION,
                RecoveryStrategy.REQUEST_CLARIFICATION,
                RecoveryStrategy.SAFE_INTERRUPT
            ],
            ErrorType.COMMUNICATION_ERROR: [
                RecoveryStrategy.RETRY_ACTION,
                RecoveryStrategy.ESCALATE_TO_OPERATOR,
                RecoveryStrategy.SAFE_INTERRUPT
            ],
            ErrorType.SAFETY_VIOLATION: [
                RecoveryStrategy.SAFE_INTERRUPT,
                RecoveryStrategy.SUGGEST_ALTERNATIVE,
                RecoveryStrategy.ESCALATE_TO_OPERATOR
            ],
            ErrorType.CAPABILITY_EXCEEDED: [
                RecoveryStrategy.SIMPLIFY_TASK,
                RecoveryStrategy.TASK_SUBSTITUTION,
                RecoveryStrategy.DELEGATE_TO_USER
            ],
            ErrorType.TEMPORAL_CONSTRAINT: [
                RecoveryStrategy.SIMPLIFY_TASK,
                RecoveryStrategy.TASK_SUBSTITUTION,
                RecoveryStrategy.DELEGATE_TO_USER
            ],
            ErrorType.RESOURCE_UNAVAILABLE: [
                RecoveryStrategy.SUGGEST_ALTERNATIVE,
                RecoveryStrategy.TASK_SUBSTITUTION,
                RecoveryStrategy.DELEGATE_TO_USER
            ]
        }

    def _initialize_handlers(self) -> Dict[RecoveryStrategy, Callable]:
        """Initialize handlers for each recovery strategy"""
        return {
            RecoveryStrategy.REQUEST_CLARIFICATION: self._handle_request_clarification,
            RecoveryStrategy.SUGGEST_ALTERNATIVE: self._handle_suggest_alternative,
            RecoveryStrategy.DELEGATE_TO_USER: self._handle_delegate_to_user,
            RecoveryStrategy.SIMPLIFY_TASK: self._handle_simplify_task,
            RecoveryStrategy.RETRY_ACTION: self._handle_retry_action,
            RecoveryStrategy.ESCALATE_TO_OPERATOR: self._handle_escalate_to_operator,
            RecoveryStrategy.SAFE_INTERRUPT: self._handle_safe_interrupt,
            RecoveryStrategy.TASK_SUBSTITUTION: self._handle_task_substitution
        }

    async def handle_error(self, error_type: ErrorType, error_message: str,
                          original_command: str, robot_state: Dict[str, Any],
                          environment_state: Dict[str, Any]) -> RecoveryAction:
        """
        Handle an error and return a recovery action

        Args:
            error_type: Type of error that occurred
            error_message: Description of the error
            original_command: Command that caused the error
            robot_state: Current state of the robot
            environment_state: Current state of the environment

        Returns:
            RecoveryAction with strategy to execute
        """
        try:
            self.logger.error(f"Handling error: {error_type.value} - {error_message}", extra={
                'error_type': error_type.value,
                'original_command': original_command
            })

            # Create recovery context
            context = ErrorRecoveryContext(
                error_type=error_type,
                error_message=error_message,
                original_command=original_command,
                robot_state=robot_state,
                environment_state=environment_state
            )

            # Add to history
            self.recovery_history.append(context)
            if len(self.recovery_history) > self.max_history_length:
                self.recovery_history = self.recovery_history[-self.max_history_length:]

            # Determine best recovery strategy
            recovery_action = await self._select_recovery_strategy(context)

            self.logger.info(f"Selected recovery strategy: {recovery_action.strategy.value}", extra={
                'strategy': recovery_action.strategy.value,
                'confidence': recovery_action.confidence
            })

            return recovery_action

        except Exception as e:
            self.logger.error(f"Error in error handling: {e}")
            # Fallback to safe interrupt
            return RecoveryAction(
                strategy=RecoveryStrategy.SAFE_INTERRUPT,
                description="Safe interrupt due to error handling failure",
                confidence=1.0
            )

    async def _select_recovery_strategy(self, context: ErrorRecoveryContext) -> RecoveryAction:
        """Select the most appropriate recovery strategy based on context"""
        available_strategies = self.recovery_strategies.get(context.error_type, [])

        # Filter out already tried strategies
        untried_strategies = [s for s in available_strategies if s not in context.recovery_strategies_tried]

        if not untried_strategies:
            # All strategies tried, escalate to operator
            return RecoveryAction(
                strategy=RecoveryStrategy.ESCALATE_TO_OPERATOR,
                description="All recovery strategies exhausted, escalating to operator",
                confidence=0.8
            )

        # Select strategy based on error type and context
        if context.error_type == ErrorType.AMBIGUOUS_COMMAND:
            return await self._select_ambiguous_command_strategy(context, untried_strategies)
        elif context.error_type == ErrorType.EXECUTION_FAILURE:
            return await self._select_execution_failure_strategy(context, untried_strategies)
        elif context.error_type == ErrorType.SAFETY_VIOLATION:
            # For safety violations, always prioritize safe interrupt
            if RecoveryStrategy.SAFE_INTERRUPT in untried_strategies:
                return RecoveryAction(
                    strategy=RecoveryStrategy.SAFE_INTERRUPT,
                    description="Safety violation - immediate safe interrupt required",
                    confidence=1.0
                )
            else:
                # If safe interrupt already tried, escalate
                return RecoveryAction(
                    strategy=RecoveryStrategy.ESCALATE_TO_OPERATOR,
                    description="Safety violation with no safe recovery path",
                    confidence=0.9
                )
        else:
            # For other error types, use the first available strategy
            strategy = untried_strategies[0]
            confidence = self._calculate_strategy_confidence(strategy, context)

            handler = self.recovery_handlers.get(strategy)
            description = await handler(context) if handler else f"Execute {strategy.value} strategy"

            return RecoveryAction(
                strategy=strategy,
                description=description,
                confidence=confidence
            )

    async def _select_ambiguous_command_strategy(self, context: ErrorRecoveryContext,
                                               available_strategies: List[RecoveryStrategy]) -> RecoveryAction:
        """Select strategy for ambiguous command errors"""
        # Prioritize clarification for ambiguous commands
        if RecoveryStrategy.REQUEST_CLARIFICATION in available_strategies:
            return RecoveryAction(
                strategy=RecoveryStrategy.REQUEST_CLARIFICATION,
                description=await self._handle_request_clarification(context),
                confidence=0.9
            )
        elif RecoveryStrategy.SUGGEST_ALTERNATIVE in available_strategies:
            return RecoveryAction(
                strategy=RecoveryStrategy.SUGGEST_ALTERNATIVE,
                description=await self._handle_suggest_alternative(context),
                confidence=0.7
            )
        else:
            # Fallback to delegation
            return RecoveryAction(
                strategy=RecoveryStrategy.DELEGATE_TO_USER,
                description=await self._handle_delegate_to_user(context),
                confidence=0.6
            )

    async def _select_execution_failure_strategy(self, context: ErrorRecoveryContext,
                                               available_strategies: List[RecoveryStrategy]) -> RecoveryAction:
        """Select strategy for execution failure errors"""
        # If this is the first attempt, try retrying
        if context.attempt_count == 1 and RecoveryStrategy.RETRY_ACTION in available_strategies:
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY_ACTION,
                description=await self._handle_retry_action(context),
                confidence=0.8
            )
        elif RecoveryStrategy.SIMPLIFY_TASK in available_strategies:
            return RecoveryAction(
                strategy=RecoveryStrategy.SIMPLIFY_TASK,
                description=await self._handle_simplify_task(context),
                confidence=0.7
            )
        else:
            return RecoveryAction(
                strategy=RecoveryStrategy.SUGGEST_ALTERNATIVE,
                description=await self._handle_suggest_alternative(context),
                confidence=0.6
            )

    def _calculate_strategy_confidence(self, strategy: RecoveryStrategy, context: ErrorRecoveryContext) -> float:
        """Calculate confidence for a recovery strategy"""
        base_confidence = {
            RecoveryStrategy.REQUEST_CLARIFICATION: 0.9,
            RecoveryStrategy.SUGGEST_ALTERNATIVE: 0.8,
            RecoveryStrategy.DELEGATE_TO_USER: 0.95,
            RecoveryStrategy.SIMPLIFY_TASK: 0.7,
            RecoveryStrategy.RETRY_ACTION: 0.6 if context.attempt_count < 3 else 0.3,
            RecoveryStrategy.ESCALATE_TO_OPERATOR: 0.9,
            RecoveryStrategy.SAFE_INTERRUPT: 1.0,
            RecoveryStrategy.TASK_SUBSTITUTION: 0.75
        }

        confidence = base_confidence.get(strategy, 0.5)

        # Adjust based on context
        if context.attempt_count > 1:
            if strategy == RecoveryStrategy.RETRY_ACTION:
                confidence *= (1.0 / context.attempt_count)  # Decrease confidence with more attempts

        return min(1.0, confidence)

    async def _handle_request_clarification(self, context: ErrorRecoveryContext) -> str:
        """Handle request for clarification strategy"""
        if context.error_type == ErrorType.AMBIGUOUS_COMMAND:
            # Analyze the ambiguous command to generate specific questions
            ambiguous_elements = self._identify_ambiguous_elements(context.original_command)
            if ambiguous_elements:
                return f"I'm not sure I understood. Could you clarify: {', '.join(ambiguous_elements)}?"
            else:
                return "I didn't quite understand that command. Could you please rephrase it?"
        else:
            return "I need some clarification to proceed. What would you like me to do differently?"

    async def _handle_suggest_alternative(self, context: ErrorRecoveryContext) -> str:
        """Handle suggest alternative strategy"""
        alternatives = self._generate_alternatives(context)
        if alternatives:
            return f"I couldn't do exactly that, but I could {random.choice(alternatives)}. Would that work?"
        else:
            return "I'm unable to perform that task. Is there something else I can help with?"

    async def _handle_delegate_to_user(self, context: ErrorRecoveryContext) -> str:
        """Handle delegate to user strategy"""
        return "I'm unable to perform this task automatically. Could you please do this manually or provide more specific instructions?"

    async def _handle_simplify_task(self, context: ErrorRecoveryContext) -> str:
        """Handle simplify task strategy"""
        simplified_task = self._simplify_task(context.original_command)
        if simplified_task:
            return f"I can't do the full task, but I can {simplified_task} instead. Would that be helpful?"
        else:
            return "I'm unable to simplify this task. Could you provide a different command?"

    async def _handle_retry_action(self, context: ErrorRecoveryContext) -> str:
        """Handle retry action strategy"""
        if context.attempt_count >= self.max_retry_attempts:
            return f"I've tried this {context.attempt_count} times without success. How should I proceed?"
        else:
            return f"I'll try that again. Attempt {context.attempt_count + 1} of {self.max_retry_attempts}."

    async def _handle_escalate_to_operator(self, context: ErrorRecoveryContext) -> str:
        """Handle escalate to operator strategy"""
        return "This requires human intervention. I'm connecting you with an operator now."

    async def _handle_safe_interrupt(self, context: ErrorRecoveryContext) -> str:
        """Handle safe interrupt strategy"""
        return "Safety concern detected. I'm stopping current operations and returning to a safe state."

    async def _handle_task_substitution(self, context: ErrorRecoveryContext) -> str:
        """Handle task substitution strategy"""
        substitution = self._find_task_substitution(context.original_command)
        if substitution:
            return f"I can't do that, but I can {substitution} instead. Would that work?"
        else:
            return "I can't perform this task. Is there a different task I can help with?"

    def _identify_ambiguous_elements(self, command: str) -> List[str]:
        """Identify ambiguous elements in a command"""
        ambiguous_indicators = []

        # Look for vague spatial references
        if any(word in command.lower() for word in ['it', 'that', 'there', 'this', 'thing', 'object']):
            ambiguous_indicators.append("what specific object you mean")

        # Look for vague temporal references
        if any(word in command.lower() for word in ['now', 'soon', 'later', 'when convenient']):
            ambiguous_indicators.append("when exactly you want this done")

        # Look for vague spatial locations
        if any(word in command.lower() for word in ['there', 'over there', 'somewhere', 'around']):
            ambiguous_indicators.append("the specific location")

        return ambiguous_indicators

    def _generate_alternatives(self, context: ErrorRecoveryContext) -> List[str]:
        """Generate alternative actions based on context"""
        alternatives = []

        if context.error_type == ErrorType.CAPABILITY_EXCEEDED:
            # If robot can't reach, suggest bringing object closer
            alternatives.extend([
                "move the object to a more accessible location",
                "perform a simpler version of the task",
                "ask someone to place the object within my reach"
            ])
        elif context.error_type == ErrorType.RESOURCE_UNAVAILABLE:
            # If resources unavailable, suggest alternatives
            alternatives.extend([
                "use a different object",
                "wait until resources become available",
                "find an alternative method to achieve the goal"
            ])
        elif context.error_type == ErrorType.EXECUTION_FAILURE:
            alternatives.extend([
                "try a different approach",
                "simplify the task",
                "perform the task at a different time or location"
            ])

        return alternatives

    def _simplify_task(self, original_command: str) -> Optional[str]:
        """Suggest a simplified version of the task"""
        command_lower = original_command.lower()

        # Simplify complex navigation
        if any(word in command_lower for word in ['navigate', 'go to', 'move to']):
            return "move to a nearby location"

        # Simplify complex manipulation
        if any(word in command_lower for word in ['manipulate', 'handle', 'work with']):
            return "move the object slightly"

        # Simplify cleaning tasks
        if any(word in command_lower for word in ['clean', 'organize', 'arrange']):
            return "move one object to a different position"

        return None

    def _find_task_substitution(self, original_command: str) -> Optional[str]:
        """Find a substitute task that achieves a similar goal"""
        command_lower = original_command.lower()

        if 'pick' in command_lower or 'grasp' in command_lower:
            return "point to the object instead"
        elif 'move' in command_lower or 'transport' in command_lower:
            return "indicate the destination location"
        elif 'clean' in command_lower:
            return "organize the objects in place"
        elif 'assemble' in command_lower:
            return "sort the components by type"

        return None

    async def execute_recovery_action(self, recovery_action: RecoveryAction,
                                    context: ErrorRecoveryContext) -> Tuple[bool, str]:
        """
        Execute a recovery action

        Args:
            recovery_action: The action to execute
            context: The error recovery context

        Returns:
            Tuple of (success, result_description)
        """
        try:
            self.logger.info(f"Executing recovery action: {recovery_action.strategy.value}", extra={
                'strategy': recovery_action.strategy.value
            })

            # Mark this strategy as tried
            if recovery_action.strategy not in context.recovery_strategies_tried:
                context.recovery_strategies_tried.append(recovery_action.strategy)

            # Execute based on strategy
            if recovery_action.strategy == RecoveryStrategy.REQUEST_CLARIFICATION:
                # This would typically involve getting input from the user
                return True, recovery_action.description
            elif recovery_action.strategy == RecoveryStrategy.RETRY_ACTION:
                # Increment attempt count
                context.attempt_count += 1
                return True, recovery_action.description
            elif recovery_action.strategy == RecoveryStrategy.SAFE_INTERRUPT:
                # Perform safe interrupt operations
                self._perform_safe_interrupt()
                return True, "Robot safely interrupted and returned to safe state"
            elif recovery_action.strategy == RecoveryStrategy.ESCALATE_TO_OPERATOR:
                # This would involve alerting an operator
                self._alert_operator(context)
                return True, "Operator notified of the issue"
            else:
                # For other strategies, just return the description
                return True, recovery_action.description

        except Exception as e:
            self.logger.error(f"Error executing recovery action: {e}")
            return False, f"Failed to execute recovery action: {str(e)}"

    def _perform_safe_interrupt(self):
        """Perform safe interrupt operations"""
        # In a real implementation, this would:
        # - Stop all current robot motion
        # - Return to a safe home position
        # - Deactivate end effectors
        # - Log the interrupt event
        self.logger.info("Performing safe interrupt operations")

    def _alert_operator(self, context: ErrorRecoveryContext):
        """Alert operator about the error"""
        # In a real implementation, this would:
        # - Send notification to operator interface
        # - Provide error details
        # - Suggest possible actions
        self.logger.info(f"Alerting operator about error: {context.error_message}")

    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get statistics about error recovery"""
        if not self.recovery_history:
            return {"total_errors": 0}

        error_counts = {}
        strategy_counts = {}
        success_count = 0

        for recovery in self.recovery_history:
            error_type = recovery.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # Calculate average confidence
        if self.recovery_history:
            avg_confidence = sum(
                0.5 for r in self.recovery_history  # Placeholder - would need actual confidence tracking
            ) / len(self.recovery_history)
        else:
            avg_confidence = 0.0

        return {
            "total_errors": len(self.recovery_history),
            "error_type_distribution": error_counts,
            "average_confidence": avg_confidence,
            "recent_errors": [r.error_type.value for r in self.recovery_history[-10:]]
        }

    def reset_recovery_history(self):
        """Reset the recovery history"""
        self.recovery_history = []
        self.logger.info("Recovery history reset")


class RecoveryValidator:
    """Validates recovery actions for safety and feasibility"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_recovery_action(self, recovery_action: RecoveryAction,
                               robot_capabilities: Dict[str, Any],
                               environment_constraints: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a recovery action for safety and feasibility

        Args:
            recovery_action: The recovery action to validate
            robot_capabilities: Robot's current capabilities
            environment_constraints: Current environment constraints

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check if strategy is supported by robot
        if not self._strategy_supported_by_robot(recovery_action.strategy, robot_capabilities):
            issues.append(f"Recovery strategy {recovery_action.strategy.value} not supported by robot capabilities")

        # Check safety constraints
        if not self._check_safety_constraints(recovery_action.strategy, environment_constraints):
            issues.append(f"Recovery strategy {recovery_action.strategy.value} may violate safety constraints")

        # Check resource availability
        if not self._check_resource_availability(recovery_action.strategy, robot_capabilities):
            issues.append(f"Insufficient resources for recovery strategy {recovery_action.strategy.value}")

        is_valid = len(issues) == 0
        return is_valid, issues

    def _strategy_supported_by_robot(self, strategy: RecoveryStrategy, capabilities: Dict[str, Any]) -> bool:
        """Check if robot supports the recovery strategy"""
        if strategy in [RecoveryStrategy.SAFE_INTERRUPT, RecoveryStrategy.DELEGATE_TO_USER]:
            # These are always supported
            return True
        elif strategy == RecoveryStrategy.RETRY_ACTION:
            return capabilities.get('mobility', False) or capabilities.get('manipulation', False)
        elif strategy in [RecoveryStrategy.SIMPLIFY_TASK, RecoveryStrategy.SUGGEST_ALTERNATIVE]:
            return capabilities.get('communication', False)
        elif strategy == RecoveryStrategy.REQUEST_CLARIFICATION:
            return capabilities.get('communication', False)
        else:
            return True  # Conservative assumption

    def _check_safety_constraints(self, strategy: RecoveryStrategy, constraints: Dict[str, Any]) -> bool:
        """Check if strategy violates safety constraints"""
        # For safety violation errors, only safe interrupt should be allowed
        # This is a simplified check - in practice, you'd have more complex safety logic
        return True  # Placeholder implementation

    def _check_resource_availability(self, strategy: RecoveryStrategy, capabilities: Dict[str, Any]) -> bool:
        """Check if required resources are available"""
        # Check battery level for mobility-related strategies
        if strategy in [RecoveryStrategy.RETRY_ACTION, RecoveryStrategy.SIMPLIFY_TASK]:
            battery_level = capabilities.get('battery_level', 100)
            if battery_level < 20:  # Low battery threshold
                return False
        return True


# Example usage and testing
async def test_error_recovery():
    """Test the error recovery system"""
    print("Testing Error Recovery System")
    print("=" * 40)

    recovery_manager = ErrorRecoveryManager()
    validator = RecoveryValidator()

    # Test different error scenarios
    test_scenarios = [
        {
            "error_type": ErrorType.AMBIGUOUS_COMMAND,
            "error_message": "Command is ambiguous",
            "original_command": "Move it to there",
            "robot_state": {"position": "home", "battery": 80, "gripper": "open"},
            "environment_state": {"objects": ["object_1", "object_2"], "obstacles": []}
        },
        {
            "error_type": ErrorType.EXECUTION_FAILURE,
            "error_message": "Failed to grasp object",
            "original_command": "Pick up the red cup",
            "robot_state": {"position": "at_object", "gripper": "failed", "battery": 75},
            "environment_state": {"objects": ["red_cup"], "obstacles": []}
        },
        {
            "error_type": ErrorType.SAFETY_VIOLATION,
            "error_message": "Path contains human",
            "original_command": "Navigate to kitchen",
            "robot_state": {"position": "living_room", "battery": 90},
            "environment_state": {"objects": [], "obstacles": ["human_detected"]}
        },
        {
            "error_type": ErrorType.CAPABILITY_EXCEEDED,
            "error_message": "Object too heavy",
            "original_command": "Lift the heavy box",
            "robot_state": {"position": "at_object", "battery": 85},
            "environment_state": {"objects": ["heavy_box"], "max_payload": 1.0}
        }
    ]

    print("\nTesting error recovery scenarios:")
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['error_type'].value}: {scenario['error_message']}")
        print(f"   Command: {scenario['original_command']}")

        # Handle the error
        recovery_action = await recovery_manager.handle_error(
            scenario["error_type"],
            scenario["error_message"],
            scenario["original_command"],
            scenario["robot_state"],
            scenario["environment_state"]
        )

        print(f"   Recovery Strategy: {recovery_action.strategy.value}")
        print(f"   Description: {recovery_action.description}")
        print(f"   Confidence: {recovery_action.confidence:.2f}")

        # Validate the recovery action
        is_valid, issues = validator.validate_recovery_action(
            recovery_action,
            scenario["robot_state"],
            scenario["environment_state"]
        )
        print(f"   Valid: {is_valid}")
        if issues:
            print(f"   Issues: {', '.join(issues)}")

        # Execute the recovery action
        context = ErrorRecoveryContext(
            error_type=scenario["error_type"],
            error_message=scenario["error_message"],
            original_command=scenario["original_command"],
            robot_state=scenario["robot_state"],
            environment_state=scenario["environment_state"]
        )
        success, result = await recovery_manager.execute_recovery_action(recovery_action, context)
        print(f"   Execution: {'Success' if success else 'Failed'} - {result}")

    # Show recovery statistics
    print(f"\nRecovery Statistics:")
    stats = recovery_manager.get_recovery_statistics()
    print(f"  Total errors handled: {stats['total_errors']}")
    print(f"  Error types: {list(stats['error_type_distribution'].keys())}")

    print(f"\nError recovery system test completed!")


if __name__ == "__main__":
    asyncio.run(test_error_recovery())