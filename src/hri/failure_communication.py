"""
Failure Communication System for Human-Robot Interaction (HRI) in VLA System

This module provides clear and helpful communication when robot tasks fail,
including explanations of what went wrong and suggestions for next steps.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json


class FailureType(Enum):
    """Types of failures that can occur"""
    PERCEPTION_FAILURE = "perception_failure"
    NAVIGATION_FAILURE = "navigation_failure"
    MANIPULATION_FAILURE = "manipulation_failure"
    COMMUNICATION_FAILURE = "communication_failure"
    SAFETY_VIOLATION = "safety_violation"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    TEMPORAL_VIOLATION = "temporal_violation"
    UNKNOWN_ERROR = "unknown_error"


class CommunicationLevel(Enum):
    """Levels of communication detail"""
    BRIEF = "brief"
    DETAILED = "detailed"
    TECHNICAL = "technical"
    USER_FRIENDLY = "user_friendly"


@dataclass
class FailureReport:
    """Report of a failure event"""
    failure_type: FailureType
    error_message: str
    timestamp: datetime
    task_description: str
    robot_state: Dict[str, Any]
    environment_state: Dict[str, Any]
    confidence_in_explanation: float = 0.8
    suggested_next_steps: Optional[List[str]] = None
    recovery_attempts: int = 0


class FailureCommunicationSystem:
    """
    System for communicating failures to users in a helpful way
    Provides explanations and suggestions for resolving failures
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.explanation_templates = self._initialize_explanation_templates()
        self.suggestion_templates = self._initialize_suggestion_templates()
        self.failure_history: List[FailureReport] = []
        self.max_history_length = 100

    def _initialize_explanation_templates(self) -> Dict[FailureType, Dict[CommunicationLevel, str]]:
        """Initialize templates for explaining different types of failures"""
        return {
            FailureType.PERCEPTION_FAILURE: {
                CommunicationLevel.BRIEF: "I couldn't see or identify the object properly.",
                CommunicationLevel.USER_FRIENDLY: "I had trouble seeing the object. The lighting might be poor or the object could be hard to distinguish.",
                CommunicationLevel.DETAILED: "Object detection failed. I couldn't reliably identify the target object in my field of view. This could be due to poor lighting, occlusion, or the object not matching expected visual patterns.",
                CommunicationLevel.TECHNICAL: "Perception subsystem failed to detect/recognize target object. Confidence score below threshold, or no matching objects found in current view."
            },
            FailureType.NAVIGATION_FAILURE: {
                CommunicationLevel.BRIEF: "I couldn't reach the destination.",
                CommunicationLevel.USER_FRIENDLY: "I encountered an obstacle or the path was blocked. I couldn't find a clear way to get to where you asked me to go.",
                CommunicationLevel.DETAILED: "Navigation failed due to path planning issues. Either there was no valid path to the destination, the path was blocked by unexpected obstacles, or I couldn't safely navigate to the target location.",
                CommunicationLevel.TECHNICAL: "Path planning algorithm failed to find valid trajectory to destination. Obstacle detection may have identified impassable route, or destination outside navigable bounds."
            },
            FailureType.MANIPULATION_FAILURE: {
                CommunicationLevel.BRIEF: "I couldn't pick up or manipulate the object.",
                CommunicationLevel.USER_FRIENDLY: "I tried to pick up the object but couldn't get a good grip. It might be too heavy, too small, or in an awkward position.",
                CommunicationLevel.DETAILED: "Manipulation attempt failed. Either the object was not graspable with my current gripper configuration, the object was not in a reachable position, or force/torque sensors detected a problem during the grasp attempt.",
                CommunicationLevel.TECHNICAL: "Manipulation subsystem failed. Gripper position control, force control, or tactile feedback indicated grasp failure or inability to execute planned manipulation trajectory."
            },
            FailureType.COMMUNICATION_FAILURE: {
                CommunicationLevel.BRIEF: "Communication issue occurred.",
                CommunicationLevel.USER_FRIENDLY: "I had trouble processing your command. There might have been a misunderstanding or technical issue with speech recognition.",
                CommunicationLevel.DETAILED: "Communication processing failed. This could be due to unclear speech input, network connectivity issues, or misinterpretation of the command during natural language processing.",
                CommunicationLevel.TECHNICAL: "Communication subsystem error. Speech-to-text, NLP processing, or command parsing module returned error or confidence below threshold."
            },
            FailureType.SAFETY_VIOLATION: {
                CommunicationLevel.BRIEF: "Safety constraint prevented the action.",
                CommunicationLevel.USER_FRIENDLY: "I stopped because I detected a potential safety issue. Your safety is my top priority.",
                CommunicationLevel.DETAILED: "Action was halted due to safety system activation. Either humans were detected in the workspace, collision risk was assessed as too high, or environmental conditions were deemed unsafe for the requested action.",
                CommunicationLevel.TECHNICAL: "Safety monitoring system activated. Proximity sensors, camera-based person detection, or force/torque limits exceeded safety thresholds."
            },
            FailureType.RESOURCE_UNAVAILABLE: {
                CommunicationLevel.BRIEF: "Required resources were not available.",
                CommunicationLevel.USER_FRIENDLY: "I don't have access to everything I need right now to complete that task.",
                CommunicationLevel.DETAILED: "Task execution failed because required resources were unavailable. This could include insufficient battery power, unavailable tools/accessories, or other system resources needed for the task.",
                CommunicationLevel.TECHNICAL: "Resource manager indicated required components not available. Battery level, tool availability, or computational resources below required thresholds."
            },
            FailureType.TEMPORAL_VIOLATION: {
                CommunicationLevel.BRIEF: "The task couldn't be completed within the required time.",
                CommunicationLevel.USER_FRIENDLY: "I couldn't finish that task in the time available.",
                CommunicationLevel.DETAILED: "Task execution exceeded temporal constraints. The operation took longer than allowed by the task specification or system timeout parameters.",
                CommunicationLevel.TECHNICAL: "Task execution exceeded maximum allowed duration. Real-time constraints or timeout parameters were violated during operation."
            },
            FailureType.UNKNOWN_ERROR: {
                CommunicationLevel.BRIEF: "An unexpected error occurred.",
                CommunicationLevel.USER_FRIENDLY: "Something unexpected happened that I couldn't handle.",
                CommunicationLevel.DETAILED: "An unhandled exception or unexpected system state caused the operation to fail. The specific cause may require technical investigation.",
                CommunicationLevel.TECHNICAL: "Uncaught exception or undefined system state encountered during operation. Error type not matching known failure categories."
            }
        }

    def _initialize_suggestion_templates(self) -> Dict[FailureType, List[str]]:
        """Initialize templates for suggesting next steps after failures"""
        return {
            FailureType.PERCEPTION_FAILURE: [
                "Improve lighting in the area and try again",
                "Move the object to a location with better visibility",
                "Provide more specific information about the object's location",
                "Try describing the object differently"
            ],
            FailureType.NAVIGATION_FAILURE: [
                "Clear the path of obstacles and try again",
                "Specify an alternative destination or intermediate waypoints",
                "Check if the destination is accessible",
                "Try breaking the navigation into smaller steps"
            ],
            FailureType.MANIPULATION_FAILURE: [
                "Reposition the object to a more accessible location",
                "Try with a different object that's easier to grasp",
                "Use both hands to position the object for easier access",
                "Check if the object is too heavy or awkwardly shaped"
            ],
            FailureType.COMMUNICATION_FAILURE: [
                "Speak more clearly and slowly",
                "Reduce background noise",
                "Try rephrasing your request",
                "Use simpler language or step-by-step instructions"
            ],
            FailureType.SAFETY_VIOLATION: [
                "Ensure no people are in the robot's workspace",
                "Clear the area of potential hazards",
                "Wait until the safety issue is resolved",
                "Ask for human assistance for this task"
            ],
            FailureType.RESOURCE_UNAVAILABLE: [
                "Charge the robot and try again",
                "Make sure all required tools are available",
                "Try a less resource-intensive version of the task",
                "Schedule the task for when resources are available"
            ],
            FailureType.TEMPORAL_VIOLATION: [
                "Allow more time for the task",
                "Simplify the task requirements",
                "Break the task into multiple sessions",
                "Prioritize the most important parts of the task"
            },
            FailureType.UNKNOWN_ERROR: [
                "Try the task again",
                "Restart the system if the problem persists",
                "Contact technical support",
                "Try an alternative approach to achieve your goal"
            ]
        }

    def generate_failure_report(self, failure_type: FailureType, error_message: str,
                              task_description: str, robot_state: Dict[str, Any],
                              environment_state: Dict[str, Any],
                              recovery_attempts: int = 0) -> FailureReport:
        """
        Generate a comprehensive failure report

        Args:
            failure_type: Type of failure that occurred
            error_message: Technical error message
            task_description: Description of the task that failed
            robot_state: Current state of the robot
            environment_state: Current state of the environment
            recovery_attempts: Number of recovery attempts made

        Returns:
            FailureReport with comprehensive information
        """
        report = FailureReport(
            failure_type=failure_type,
            error_message=error_message,
            timestamp=datetime.now(),
            task_description=task_description,
            robot_state=robot_state,
            environment_state=environment_state,
            recovery_attempts=recovery_attempts,
            suggested_next_steps=self._generate_suggestions(failure_type)
        )

        # Add to history
        self.failure_history.append(report)
        if len(self.failure_history) > self.max_history_length:
            self.failure_history = self.failure_history[-self.max_history_length:]

        return report

    def _generate_suggestions(self, failure_type: FailureType) -> List[str]:
        """Generate suggestions for resolving a specific type of failure"""
        return self.suggestion_templates.get(failure_type, [
            "Try the task again",
            "Provide more specific instructions",
            "Contact technical support if the problem persists"
        ])

    def explain_failure(self, failure_report: FailureReport,
                       communication_level: CommunicationLevel = CommunicationLevel.USER_FRIENDLY) -> str:
        """
        Generate a human-friendly explanation of a failure

        Args:
            failure_report: The failure report to explain
            communication_level: Level of detail for the explanation

        Returns:
            Human-friendly explanation of the failure
        """
        try:
            template = self.explanation_templates.get(failure_report.failure_type, {}).get(communication_level)

            if template:
                explanation = template
            else:
                # Fallback to user-friendly if specific level not found
                fallback_template = self.explanation_templates.get(failure_report.failure_type, {}).get(CommunicationLevel.USER_FRIENDLY)
                explanation = fallback_template or f"An issue occurred during the task: {failure_report.error_message}"

            # Add context-specific information
            if communication_level in [CommunicationLevel.DETAILED, CommunicationLevel.TECHNICAL]:
                explanation += f" [Technical details: {failure_report.error_message}]"

            self.logger.info(f"Generated failure explanation", extra={
                'failure_type': failure_report.failure_type.value,
                'communication_level': communication_level.value
            })

            return explanation

        except Exception as e:
            self.logger.error(f"Error generating failure explanation: {e}")
            return f"I experienced an issue: {failure_report.error_message}. I'm not sure what went wrong."

    def suggest_next_steps(self, failure_report: FailureReport) -> List[str]:
        """
        Suggest next steps for the user after a failure

        Args:
            failure_report: The failure report

        Returns:
            List of suggested next steps
        """
        try:
            suggestions = failure_report.suggested_next_steps or []

            # Add task-specific suggestions
            if failure_report.failure_type == FailureType.NAVIGATION_FAILURE:
                # Add location-specific suggestions
                target_location = failure_report.task_description.split()[-1] if failure_report.task_description.split() else "destination"
                location_suggestions = [
                    f"Check if the path to {target_location} is clear of obstacles",
                    f"Verify that {target_location} is accessible and not blocked"
                ]
                suggestions.extend(location_suggestions)

            elif failure_report.failure_type == FailureType.MANIPULATION_FAILURE:
                # Add object-specific suggestions
                object_mentioned = "the object"  # Would extract from task description in practice
                object_suggestions = [
                    f"Make sure {object_mentioned} is positioned for easy access",
                    f"Check if {object_mentioned} is too heavy or awkward to handle"
                ]
                suggestions.extend(object_suggestions)

            self.logger.info(f"Suggested {len(suggestions)} next steps", extra={
                'failure_type': failure_report.failure_type.value
            })

            return suggestions

        except Exception as e:
            self.logger.error(f"Error generating next steps: {e}")
            return ["Try the task again", "Contact technical support if problems persist"]

    def generate_failure_response(self, failure_report: FailureReport,
                                communication_level: CommunicationLevel = CommunicationLevel.USER_FRIENDLY,
                                include_suggestions: bool = True) -> Dict[str, Any]:
        """
        Generate a complete response to a failure including explanation and suggestions

        Args:
            failure_report: The failure report
            communication_level: Level of detail for explanation
            include_suggestions: Whether to include next step suggestions

        Returns:
            Dictionary with complete failure response
        """
        try:
            response = {
                'failure_type': failure_report.failure_type.value,
                'explanation': self.explain_failure(failure_report, communication_level),
                'timestamp': failure_report.timestamp.isoformat(),
                'task_description': failure_report.task_description
            }

            if include_suggestions:
                response['suggestions'] = self.suggest_next_steps(failure_report)
                response['suggestion_count'] = len(response['suggestions'])

            # Add recovery information
            response['recovery_attempts'] = failure_report.recovery_attempts
            response['has_been_resolved'] = False  # This would be updated if resolved

            self.logger.info(f"Generated complete failure response", extra={
                'failure_type': failure_report.failure_type.value,
                'communication_level': communication_level.value
            })

            return response

        except Exception as e:
            self.logger.error(f"Error generating failure response: {e}")
            return {
                'failure_type': 'unknown',
                'explanation': f"I encountered an issue: {str(e)}",
                'suggestions': ["Try again or contact support"],
                'error': str(e)
            }

    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get statistics about failures"""
        if not self.failure_history:
            return {
                'total_failures': 0,
                'failure_types': {},
                'most_common_failure': None,
                'resolution_success_rate': 0.0
            }

        failure_counts = {}
        for report in self.failure_history:
            failure_type = report.failure_type.value
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1

        most_common = max(failure_counts, key=failure_counts.get) if failure_counts else None

        # Calculate resolution success rate based on recovery attempts
        total_recovery_attempts = sum(report.recovery_attempts for report in self.failure_history)
        successful_resolutions = sum(1 for report in self.failure_history if report.recovery_attempts > 0)

        return {
            'total_failures': len(self.failure_history),
            'failure_types': failure_counts,
            'most_common_failure': most_common,
            'resolution_success_rate': successful_resolutions / len(self.failure_history) if self.failure_history else 0.0,
            'total_recovery_attempts': total_recovery_attempts,
            'recent_failures': [r.failure_type.value for r in self.failure_history[-10:]]
        }

    def reset_history(self):
        """Reset the failure history"""
        self.failure_history = []
        self.logger.info("Failure history reset")


class FailureCommunicationManager:
    """Manages the failure communication process in the HRI system"""

    def __init__(self):
        self.communication_system = FailureCommunicationSystem()
        self.logger = logging.getLogger(__name__)
        self.active_failures = {}  # Track active failures that need resolution

    async def handle_failure(self, failure_type: FailureType, error_message: str,
                           task_description: str, robot_state: Dict[str, Any],
                           environment_state: Dict[str, Any],
                           communication_level: CommunicationLevel = CommunicationLevel.USER_FRIENDLY,
                           session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle a failure by generating appropriate communication

        Args:
            failure_type: Type of failure that occurred
            error_message: Technical error message
            task_description: Description of the task that failed
            robot_state: Current robot state
            environment_state: Current environment state
            communication_level: Level of detail for communication
            session_id: Session identifier for tracking

        Returns:
            Dictionary with failure handling response
        """
        try:
            self.logger.error(f"Handling failure: {failure_type.value} - {error_message}", extra={
                'failure_type': failure_type.value,
                'task_description': task_description
            })

            # Generate failure report
            failure_report = self.communication_system.generate_failure_report(
                failure_type, error_message, task_description, robot_state, environment_state
            )

            # Generate response
            response = self.communication_system.generate_failure_response(
                failure_report, communication_level
            )

            # Add session information if provided
            if session_id:
                response['session_id'] = session_id
                self.active_failures[session_id] = failure_report

            # Log the failure for statistics
            self.logger.info(f"Failure handled with {len(response.get('suggestions', []))} suggestions", extra={
                'failure_type': failure_type.value,
                'session_id': session_id
            })

            return response

        except Exception as e:
            self.logger.error(f"Error handling failure: {e}")
            return {
                'failure_type': 'unknown',
                'explanation': f"An unexpected error occurred while handling the failure: {str(e)}",
                'suggestions': ["Contact technical support"],
                'error': str(e)
            }

    async def handle_recovery_attempt(self, session_id: str, recovery_action: str) -> Dict[str, Any]:
        """
        Handle a recovery attempt for a previous failure

        Args:
            session_id: Session identifier of the original failure
            recovery_action: Action taken for recovery

        Returns:
            Dictionary with recovery handling response
        """
        try:
            if session_id not in self.active_failures:
                return {
                    'error': 'No active failure for this session',
                    'session_id': session_id
                }

            original_report = self.active_failures[session_id]

            # Update the report with recovery attempt information
            updated_report = self.communication_system.generate_failure_report(
                original_report.failure_type,
                original_report.error_message,
                original_report.task_description,
                original_report.robot_state,
                original_report.environment_state,
                recovery_attempts=original_report.recovery_attempts + 1
            )

            # Generate recovery response
            response = self.communication_system.generate_failure_response(
                updated_report,
                CommunicationLevel.USER_FRIENDLY
            )

            response['recovery_attempt'] = recovery_action
            response['recovery_attempt_number'] = updated_report.recovery_attempts

            # If recovery attempts exceed threshold, consider it permanently failed
            if updated_report.recovery_attempts >= 3:
                del self.active_failures[session_id]
                response['resolution_status'] = 'permanently_failed'
                response['final_resolution'] = True
            else:
                # Update the active failure record
                self.active_failures[session_id] = updated_report
                response['resolution_status'] = 'recovery_in_progress'
                response['final_resolution'] = False

            self.logger.info(f"Handled recovery attempt #{updated_report.recovery_attempts} for session {session_id}", extra={
                'session_id': session_id,
                'recovery_action': recovery_action
            })

            return response

        except Exception as e:
            self.logger.error(f"Error handling recovery attempt: {e}")
            return {
                'error': str(e),
                'session_id': session_id
            }

    def get_active_failures(self) -> Dict[str, Any]:
        """Get information about active failures"""
        return {
            session_id: {
                'failure_type': report.failure_type.value,
                'task_description': report.task_description,
                'recovery_attempts': report.recovery_attempts,
                'timestamp': report.timestamp.isoformat()
            }
            for session_id, report in self.active_failures.items()
        }

    async def escalate_to_human(self, session_id: str, reason: str) -> Dict[str, Any]:
        """
        Escalate a failure to human operator

        Args:
            session_id: Session identifier
            reason: Reason for escalation

        Returns:
            Dictionary with escalation response
        """
        try:
            if session_id not in self.active_failures:
                return {
                    'error': 'No active failure for this session',
                    'session_id': session_id
                }

            original_report = self.active_failures[session_id]

            response = {
                'escalation_requested': True,
                'session_id': session_id,
                'original_failure': original_report.failure_type.value,
                'task_description': original_report.task_description,
                'reason_for_escalation': reason,
                'robot_state': original_report.robot_state,
                'environment_state': original_report.environment_state,
                'recovery_attempts': original_report.recovery_attempts
            }

            # Remove from active failures as it's now escalated
            del self.active_failures[session_id]

            self.logger.info(f"Escalated failure to human operator for session {session_id}", extra={
                'session_id': session_id,
                'reason': reason
            })

            return response

        except Exception as e:
            self.logger.error(f"Error escalating to human: {e}")
            return {
                'error': str(e),
                'session_id': session_id
            }


# Example usage and testing
async def test_failure_communication():
    """Test the failure communication system"""
    print("Testing Failure Communication System")
    print("=" * 50)

    comm_manager = FailureCommunicationManager()

    # Test different failure scenarios
    test_failures = [
        {
            "type": FailureType.NAVIGATION_FAILURE,
            "error": "Path planning failed: obstacle detected",
            "task": "navigate to kitchen",
            "robot_state": {"position": "living_room", "battery": 80},
            "environment_state": {"obstacles": ["chair", "person"], "clear_path": False}
        },
        {
            "type": FailureType.MANIPULATION_FAILURE,
            "error": "Grasp failed: object too heavy",
            "task": "pick up heavy box",
            "robot_state": {"gripper_position": "at_object", "force_sensors": "maxed_out"},
            "environment_state": {"object_weight": 5.0, "max_capacity": 2.0}
        },
        {
            "type": FailureType.PERCEPTION_FAILURE,
            "error": "Object detection confidence below threshold",
            "task": "find red cup",
            "robot_state": {"camera_status": "active", "detection_results": []},
            "environment_state": {"lighting": "dim", "objects": ["various_items"]}
        },
        {
            "type": FailureType.SAFETY_VIOLATION,
            "error": "Human detected in workspace",
            "task": "move arm to pick up object",
            "robot_state": {"arm_position": "moving", "safety_status": "violated"},
            "environment_state": {"humans_detected": ["person_1"], "workspace_clear": False}
        }
    ]

    print("\nTesting failure communication for different scenarios:")
    for i, failure in enumerate(test_failures, 1):
        print(f"\n{i}. {failure['type'].value}: {failure['error']}")
        print(f"   Task: {failure['task']}")

        # Handle the failure
        response = await comm_manager.handle_failure(
            failure["type"],
            failure["error"],
            failure["task"],
            failure["robot_state"],
            failure["environment_state"],
            session_id=f"session_{i}"
        )

        print(f"   Explanation: {response['explanation']}")
        print(f"   Suggestions ({len(response.get('suggestions', []))}):")
        for j, suggestion in enumerate(response.get('suggestions', [])[:2], 1):  # Show first 2
            print(f"     {j}. {suggestion}")

        # Simulate a recovery attempt
        if response.get('suggestions'):
            recovery_response = await comm_manager.handle_recovery_attempt(
                f"session_{i}",
                response['suggestions'][0]
            )
            print(f"   Recovery attempt: {recovery_response.get('recovery_attempt', 'N/A')}")

    # Show failure statistics
    print(f"\nFailure Statistics:")
    stats = comm_manager.communication_system.get_failure_statistics()
    print(f"  Total failures handled: {stats['total_failures']}")
    print(f"  Most common failure: {stats['most_common_failure']}")
    print(f"  Resolution success rate: {stats['resolution_success_rate']:.1%}")

    # Show active failures
    print(f"\nActive Failures:")
    active = comm_manager.get_active_failures()
    print(f"  Count: {len(active)}")
    for session_id, info in active.items():
        print(f"  {session_id}: {info['failure_type']} - {info['task_description']}")

    print(f"\nFailure communication system test completed!")


if __name__ == "__main__":
    asyncio.run(test_failure_communication())