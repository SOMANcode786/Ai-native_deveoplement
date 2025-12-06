"""
LLM Response Validator for Vision-Language-Action (VLA) System

This module provides comprehensive validation for LLM responses in the context
of robotic planning and control, ensuring safety, feasibility, and correctness.
"""

import json
import re
from typing import Dict, Any, List, Optional, Union, Tuple
import logging
from dataclasses import dataclass
from enum import Enum


class ValidationResult(Enum):
    """Result of validation"""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationIssue:
    """Represents an issue found during validation"""
    severity: ValidationResult
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    path: Optional[str] = None


class LLMResponseValidator:
    """
    Validates LLM responses for VLA system applications
    Checks for format, safety, feasibility, and correctness
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_rules = self._initialize_validation_rules()

    def _initialize_validation_rules(self) -> Dict[str, Any]:
        """Initialize validation rules for different response types"""
        return {
            "action_sequence": {
                "required_fields": ["action_type", "parameters", "description"],
                "valid_action_types": [
                    "navigate", "move_to", "grasp", "place", "detect_object",
                    "identify", "move_object", "speak", "wait", "deliver"
                ],
                "parameter_validators": {
                    "x": self._validate_coordinate,
                    "y": self._validate_coordinate,
                    "z": self._validate_coordinate,
                    "force": self._validate_force,
                    "object_id": self._validate_object_id,
                    "target_location": self._validate_location
                }
            },
            "navigation_plan": {
                "required_fields": ["path", "safety_analysis"],
                "path_validators": {
                    "coordinates": self._validate_path_coordinates,
                    "feasibility": self._validate_path_feasibility
                }
            },
            "perception_analysis": {
                "required_fields": ["objects_detected", "task_relevant_objects"],
                "object_validators": {
                    "position": self._validate_object_position,
                    "confidence": self._validate_confidence
                }
            }
        }

    def validate_response(self, response: str, response_type: str = "action_sequence",
                         context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate an LLM response based on its type

        Args:
            response: The LLM response string
            response_type: Type of response to validate
            context: Additional context for validation

        Returns:
            Dictionary with validation results
        """
        try:
            # Parse the response
            parsed_response = self._parse_response(response)
            if parsed_response is None:
                return {
                    "valid": False,
                    "issues": [ValidationIssue(
                        severity=ValidationResult.ERROR,
                        code="PARSE_ERROR",
                        message="Failed to parse response as JSON"
                    )],
                    "original_response": response
                }

            # Validate based on response type
            if response_type in self.validation_rules:
                return self._validate_by_type(parsed_response, response_type, context)
            else:
                # Generic validation
                return self._validate_generic_response(parsed_response, context)

        except Exception as e:
            self.logger.error(f"Error validating response: {e}")
            return {
                "valid": False,
                "issues": [ValidationIssue(
                    severity=ValidationResult.ERROR,
                    code="VALIDATION_ERROR",
                    message=f"Error during validation: {str(e)}"
                )],
                "original_response": response
            }

    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response string to JSON"""
        try:
            # Try to extract JSON from the response (in case there's extra text)
            json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        try:
            # Direct parse if it's clean JSON
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        return None

    def _validate_by_type(self, response: Dict[str, Any], response_type: str,
                         context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate response based on its specific type"""
        issues = []
        rules = self.validation_rules[response_type]

        # Check required fields
        for field in rules.get("required_fields", []):
            if field not in response:
                issues.append(ValidationIssue(
                    severity=ValidationResult.ERROR,
                    code="MISSING_FIELD",
                    message=f"Missing required field: {field}",
                    details={"missing_field": field}
                ))

        # Apply type-specific validation
        if response_type == "action_sequence":
            issues.extend(self._validate_action_sequence(response, context))
        elif response_type == "navigation_plan":
            issues.extend(self._validate_navigation_plan(response, context))
        elif response_type == "perception_analysis":
            issues.extend(self._validate_perception_analysis(response, context))

        # Check for valid structure
        is_valid = not any(issue.severity == ValidationResult.ERROR for issue in issues)

        return {
            "valid": is_valid,
            "issues": issues,
            "response": response,
            "type": response_type
        }

    def _validate_generic_response(self, response: Dict[str, Any],
                                  context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generic validation for unknown response types"""
        issues = []

        # Check if it's a dictionary
        if not isinstance(response, dict):
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_STRUCTURE",
                message="Response must be a dictionary",
                details={"response_type": type(response).__name__}
            ))

        is_valid = len(issues) == 0
        return {
            "valid": is_valid,
            "issues": issues,
            "response": response,
            "type": "generic"
        }

    def _validate_action_sequence(self, response: Dict[str, Any],
                                 context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate action sequence response"""
        issues = []

        # Check if 'action_sequence' exists (common format) or if response is the sequence
        actions = response.get('action_sequence', response if isinstance(response, list) else [])

        if isinstance(actions, dict) and 'action_sequence' in actions:
            actions = actions['action_sequence']

        if not isinstance(actions, list):
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_ACTION_SEQUENCE",
                message="Action sequence must be a list",
                details={"sequence_type": type(actions).__name__}
            ))
            return issues

        # Validate each action
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                issues.append(ValidationIssue(
                    severity=ValidationResult.ERROR,
                    code="INVALID_ACTION_FORMAT",
                    message=f"Action at index {i} is not a dictionary",
                    details={"action_index": i, "action_type": type(action).__name__}
                ))
                continue

            # Check required fields
            required_fields = self.validation_rules["action_sequence"]["required_fields"]
            for field in required_fields:
                if field not in action:
                    issues.append(ValidationIssue(
                        severity=ValidationResult.ERROR,
                        code="MISSING_ACTION_FIELD",
                        message=f"Action at index {i} missing required field: {field}",
                        details={"action_index": i, "missing_field": field}
                    ))

            # Validate action type
            action_type = action.get('action_type', '')
            if action_type not in self.validation_rules["action_sequence"]["valid_action_types"]:
                issues.append(ValidationIssue(
                    severity=ValidationResult.WARNING,
                    code="UNKNOWN_ACTION_TYPE",
                    message=f"Action at index {i} has unknown action type: {action_type}",
                    details={"action_index": i, "action_type": action_type}
                ))

            # Validate parameters
            parameters = action.get('parameters', {})
            if not isinstance(parameters, dict):
                issues.append(ValidationIssue(
                    severity=ValidationResult.ERROR,
                    code="INVALID_PARAMETERS",
                    message=f"Action at index {i} has invalid parameters",
                    details={"action_index": i, "parameters_type": type(parameters).__name__}
                ))

            # Apply parameter-specific validation
            for param_name, param_value in parameters.items():
                validator = self.validation_rules["action_sequence"]["parameter_validators"].get(param_name)
                if validator:
                    param_issues = validator(param_value, context)
                    for issue in param_issues:
                        issue.path = f"action[{i}].parameters.{param_name}"
                        issues.append(issue)

        # Check for safety and feasibility
        issues.extend(self._check_action_sequence_safety(actions, context))

        return issues

    def _validate_navigation_plan(self, response: Dict[str, Any],
                                 context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate navigation plan response"""
        issues = []

        # Validate path
        path = response.get('path', [])
        if not isinstance(path, list):
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_PATH",
                message="Navigation path must be a list",
                details={"path_type": type(path).__name__}
            ))
        else:
            for i, waypoint in enumerate(path):
                if not isinstance(waypoint, dict):
                    issues.append(ValidationIssue(
                        severity=ValidationResult.ERROR,
                        code="INVALID_WAYPOINT",
                        message=f"Waypoint at index {i} is not a dictionary",
                        details={"waypoint_index": i, "waypoint_type": type(waypoint).__name__}
                    ))
                    continue

                # Check required waypoint fields
                for field in ['x', 'y']:
                    if field not in waypoint:
                        issues.append(ValidationIssue(
                            severity=ValidationResult.ERROR,
                            code="MISSING_WAYPOINT_FIELD",
                            message=f"Waypoint at index {i} missing required field: {field}",
                            details={"waypoint_index": i, "missing_field": field}
                        ))

        # Validate safety analysis
        safety_analysis = response.get('safety_analysis', {})
        if not isinstance(safety_analysis, dict):
            issues.append(ValidationIssue(
                severity=ValidationResult.WARNING,
                code="INVALID_SAFETY_ANALYSIS",
                message="Safety analysis should be a dictionary",
                details={"safety_analysis_type": type(safety_analysis).__name__}
            ))

        return issues

    def _validate_perception_analysis(self, response: Dict[str, Any],
                                     context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate perception analysis response"""
        issues = []

        # Validate objects detected
        objects = response.get('objects_detected', [])
        if not isinstance(objects, list):
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_OBJECTS_LIST",
                message="Objects detected must be a list",
                details={"objects_type": type(objects).__name__}
            ))
        else:
            for i, obj in enumerate(objects):
                if not isinstance(obj, dict):
                    issues.append(ValidationIssue(
                        severity=ValidationResult.ERROR,
                        code="INVALID_OBJECT_FORMAT",
                        message=f"Object at index {i} is not a dictionary",
                        details={"object_index": i, "object_type": type(obj).__name__}
                    ))
                    continue

                # Validate object properties
                obj_issues = self._validate_object_properties(obj, context)
                for issue in obj_issues:
                    issue.path = f"objects_detected[{i}]"
                    issues.append(issue)

        return issues

    def _validate_object_properties(self, obj: Dict[str, Any],
                                   context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate individual object properties"""
        issues = []

        # Validate position
        position = obj.get('position', {})
        if isinstance(position, dict):
            for coord in ['x', 'y', 'z']:
                if coord in position:
                    coord_val = position[coord]
                    if not isinstance(coord_val, (int, float)):
                        issues.append(ValidationIssue(
                            severity=ValidationResult.ERROR,
                            code="INVALID_COORDINATE",
                            message=f"Invalid {coord} coordinate value: {coord_val}",
                            details={"coordinate": coord, "value": coord_val}
                        ))

        # Validate confidence
        confidence = obj.get('confidence')
        if confidence is not None:
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                issues.append(ValidationIssue(
                    severity=ValidationResult.ERROR,
                    code="INVALID_CONFIDENCE",
                    message=f"Confidence must be between 0 and 1, got: {confidence}",
                    details={"confidence": confidence}
                ))

        return issues

    def _check_action_sequence_safety(self, actions: List[Dict[str, Any]],
                                     context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Check action sequence for safety issues"""
        issues = []

        # Get robot capabilities from context
        robot_caps = context.get('robot_capabilities', {}) if context else {}
        max_payload = robot_caps.get('max_payload', float('inf'))

        for i, action in enumerate(actions):
            action_type = action.get('action_type', '').lower()
            parameters = action.get('parameters', {})

            # Check for payload issues
            if action_type in ['grasp', 'pick_up', 'lift'] and 'object_weight' in parameters:
                obj_weight = parameters['object_weight']
                if obj_weight > max_payload:
                    issues.append(ValidationIssue(
                        severity=ValidationResult.ERROR,
                        code="OVER_PAYLOAD",
                        message=f"Action at index {i} exceeds robot payload capacity",
                        details={
                            "action_index": i,
                            "object_weight": obj_weight,
                            "max_payload": max_payload
                        }
                    ))

            # Check for impossible locations
            target_location = parameters.get('target_location')
            if target_location and context:
                valid_locations = context.get('environment', {}).get('locations', [])
                if target_location not in valid_locations and target_location != 'unknown':
                    issues.append(ValidationIssue(
                        severity=ValidationResult.WARNING,
                        code="UNKNOWN_LOCATION",
                        message=f"Action at index {i} references unknown location: {target_location}",
                        details={
                            "action_index": i,
                            "location": target_location,
                            "valid_locations": valid_locations
                        }
                    ))

        return issues

    # Parameter validators
    def _validate_coordinate(self, value: Any, context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate coordinate values"""
        issues = []
        if not isinstance(value, (int, float)):
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_COORDINATE_TYPE",
                message=f"Coordinate must be number, got {type(value).__name__}",
                details={"value": value, "expected_type": "number"}
            ))
        elif not (-100 <= value <= 100):  # Reasonable workspace limits
            issues.append(ValidationIssue(
                severity=ValidationResult.WARNING,
                code="COORDINATE_OUT_OF_BOUNDS",
                message=f"Coordinate {value} seems out of typical workspace bounds",
                details={"value": value}
            ))
        return issues

    def _validate_force(self, value: Any, context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate force values"""
        issues = []
        if not isinstance(value, (int, float)):
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_FORCE_TYPE",
                message=f"Force must be number, got {type(value).__name__}",
                details={"value": value, "expected_type": "number"}
            ))
        elif value < 0 or value > 100:  # Reasonable force limits
            issues.append(ValidationIssue(
                severity=ValidationResult.WARNING,
                code="FORCE_OUT_OF_RANGE",
                message=f"Force value {value}N seems out of typical range",
                details={"value": value}
            ))
        return issues

    def _validate_object_id(self, value: Any, context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate object ID"""
        issues = []
        if not isinstance(value, str) or not value.strip():
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_OBJECT_ID",
                message=f"Object ID must be non-empty string, got {type(value).__name__}",
                details={"value": value, "expected_type": "string"}
            ))
        return issues

    def _validate_location(self, value: Any, context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate location"""
        issues = []
        if not isinstance(value, str) or not value.strip():
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_LOCATION",
                message=f"Location must be non-empty string, got {type(value).__name__}",
                details={"value": value, "expected_type": "string"}
            ))
        return issues

    def _validate_path_coordinates(self, path: List[Dict[str, Any]],
                                  context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate path coordinates"""
        issues = []
        for i, waypoint in enumerate(path):
            for coord in ['x', 'y', 'z']:
                if coord in waypoint:
                    val = waypoint[coord]
                    if not isinstance(val, (int, float)):
                        issues.append(ValidationIssue(
                            severity=ValidationResult.ERROR,
                            code="INVALID_WAYPOINT_COORD",
                            message=f"Waypoint {i} coordinate {coord} is invalid: {val}",
                            details={"waypoint_index": i, "coordinate": coord, "value": val}
                        ))
        return issues

    def _validate_path_feasibility(self, path: List[Dict[str, Any]],
                                  context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate path feasibility"""
        issues = []
        # In a real system, this would check for collisions, kinematic feasibility, etc.
        return issues

    def _validate_object_position(self, position: Dict[str, Any],
                                 context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate object position"""
        issues = []
        for coord in ['x', 'y', 'z']:
            if coord in position:
                val = position[coord]
                if not isinstance(val, (int, float)):
                    issues.append(ValidationIssue(
                        severity=ValidationResult.ERROR,
                        code="INVALID_OBJECT_COORD",
                        message=f"Object coordinate {coord} is invalid: {val}",
                        details={"coordinate": coord, "value": val}
                    ))
        return issues

    def _validate_confidence(self, value: Any,
                           context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate confidence value"""
        issues = []
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            issues.append(ValidationIssue(
                severity=ValidationResult.ERROR,
                code="INVALID_CONFIDENCE_VALUE",
                message=f"Confidence must be between 0 and 1, got: {value}",
                details={"value": value}
            ))
        return issues


class ValidationReporter:
    """Generates reports from validation results"""

    @staticmethod
    def generate_summary(validation_result: Dict[str, Any]) -> str:
        """Generate a summary of validation results"""
        if not validation_result.get('valid', False):
            issues = validation_result.get('issues', [])
            error_count = sum(1 for issue in issues if issue.severity == ValidationResult.ERROR)
            warning_count = sum(1 for issue in issues if issue.severity == ValidationResult.WARNING)

            return f"Validation FAILED with {error_count} errors and {warning_count} warnings"
        else:
            return "Validation PASSED"

    @staticmethod
    def generate_detailed_report(validation_result: Dict[str, Any]) -> str:
        """Generate a detailed validation report"""
        report_lines = []

        is_valid = validation_result.get('valid', False)
        report_lines.append(f"Validation Result: {'PASS' if is_valid else 'FAIL'}")
        report_lines.append(f"Response Type: {validation_result.get('type', 'unknown')}")

        issues = validation_result.get('issues', [])
        if issues:
            report_lines.append("\nIssues Found:")
            for issue in issues:
                severity_symbol = {
                    ValidationResult.ERROR: "❌",
                    ValidationResult.WARNING: "⚠️",
                    ValidationResult.VALID: "✅",
                    ValidationResult.WARNING: "ℹ️"
                }.get(issue.severity, "?")

                location = f" ({issue.path})" if issue.path else ""
                report_lines.append(f"  {severity_symbol} {issue.code}: {issue.message}{location}")
        else:
            report_lines.append("\nNo issues found!")

        return "\n".join(report_lines)


# Example usage and testing
def create_validation_demo():
    """Demonstrate the validation capabilities"""
    print("LLM Response Validator Demo")
    print("=" * 40)

    validator = LLMResponseValidator()
    reporter = ValidationReporter()

    # Example 1: Valid action sequence
    print("\n1. Valid action sequence:")
    valid_response = '''
    [
        {
            "action_type": "detect_object",
            "parameters": {"object_type": "cup", "color": "red"},
            "description": "Detect a red cup"
        },
        {
            "action_type": "move_to",
            "parameters": {"target_location": "table", "x": 1.0, "y": 2.0, "z": 0.0},
            "description": "Move to the table"
        }
    ]
    '''

    result1 = validator.validate_response(valid_response, "action_sequence")
    print(f"   Result: {reporter.generate_summary(result1)}")
    print(f"   Issues: {len(result1.get('issues', []))}")

    # Example 2: Invalid action sequence (missing field)
    print("\n2. Invalid action sequence (missing field):")
    invalid_response = '''
    [
        {
            "action_type": "detect_object",
            "parameters": {"object_type": "cup", "color": "red"}
            // Missing description field
        }
    ]
    '''

    result2 = validator.validate_response(invalid_response, "action_sequence")
    print(f"   Result: {reporter.generate_summary(result2)}")
    print(f"   Issues: {len(result2.get('issues', []))}")
    if result2.get('issues'):
        print(f"   First issue: {result2['issues'][0].message}")

    # Example 3: Navigation plan
    print("\n3. Navigation plan validation:")
    nav_response = '''
    {
        "path": [
            {"x": 0.0, "y": 0.0, "theta": 0.0},
            {"x": 1.0, "y": 1.0, "theta": 0.0}
        ],
        "safety_analysis": {
            "collision_risk": "low",
            "alternative_routes": []
        }
    }
    '''

    result3 = validator.validate_response(nav_response, "navigation_plan")
    print(f"   Result: {reporter.generate_summary(result3)}")
    print(f"   Issues: {len(result3.get('issues', []))}")

    # Example 4: With context validation
    print("\n4. Context-aware validation:")
    context = {
        "robot_capabilities": {
            "max_payload": 2.0
        },
        "environment": {
            "locations": ["table", "kitchen_counter", "shelf"]
        }
    }

    risky_response = '''
    [
        {
            "action_type": "grasp",
            "parameters": {"object_id": "heavy_box", "object_weight": 5.0},
            "description": "Grasp heavy box"
        }
    ]
    '''

    result4 = validator.validate_response(risky_response, "action_sequence", context)
    print(f"   Result: {reporter.generate_summary(result4)}")
    print(f"   Issues: {len(result4.get('issues', []))}")
    if result4.get('issues'):
        for issue in result4['issues']:
            print(f"   - {issue.message}")

    print(f"\nLLM Response Validator demo completed!")


if __name__ == "__main__":
    create_validation_demo()