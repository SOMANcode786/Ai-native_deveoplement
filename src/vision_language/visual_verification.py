"""
Visual Verification System for Vision-Language-Action (VLA) System

This module provides visual verification capabilities to confirm that robot actions
were executed successfully and to validate task completion in the VLA system.
"""

import asyncio
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import cv2
import math

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    from torchvision.models.detection import fasterrcnn_resnet50_fpn
    TORCHVISION_AVAILABLE = True
except ImportError:
    TORCHVISION_AVAILABLE = False
    fasterrcnn_resnet50_fpn = None


class VerificationStatus(Enum):
    """Status of visual verification"""
    SUCCESS = "success"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    UNCERTAIN = "uncertain"


class VerificationType(Enum):
    """Types of visual verification"""
    OBJECT_DETECTION = "object_detection"
    POSITION_CHANGE = "position_change"
    STATE_CHANGE = "state_change"
    COUNT_CHANGE = "count_change"
    SPATIAL_RELATION = "spatial_relation"
    COMPLETION = "completion"


@dataclass
class VerificationResult:
    """Result of visual verification"""
    status: VerificationStatus
    confidence: float
    verification_type: VerificationType
    description: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


class VisualVerificationSystem:
    """
    Core system for visual verification of robot actions
    Confirms task completion and validates action outcomes
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.object_detector = None
        self.feature_matcher = None
        self.init_success = self._initialize_components()

    def _initialize_components(self) -> bool:
        """Initialize verification components"""
        try:
            # Initialize object detector if available
            if TORCHVISION_AVAILABLE:
                self.object_detector = fasterrcnn_resnet50_fpn(pretrained=True)
                self.object_detector.eval()
                self.logger.info("Object detector initialized for verification")

            # Initialize feature matcher using OpenCV
            try:
                self.feature_matcher = cv2.SIFT_create()
                self.logger.info("Feature matcher initialized")
            except AttributeError:
                # SIFT might not be available due to patent restrictions
                # Use ORB as fallback
                self.feature_matcher = cv2.ORB_create()
                self.logger.info("Feature matcher (ORB) initialized")

            return True
        except Exception as e:
            self.logger.error(f"Error initializing verification components: {e}")
            return False

    async def verify_action_completion(self, action_description: str,
                                     before_image: np.ndarray,
                                     after_image: np.ndarray,
                                     parameters: Optional[Dict[str, Any]] = None) -> VerificationResult:
        """
        Verify that an action was completed successfully by comparing before/after images

        Args:
            action_description: Description of the action that was performed
            before_image: Image before the action
            after_image: Image after the action
            parameters: Additional parameters for the verification

        Returns:
            Verification result with status and confidence
        """
        try:
            self.logger.info(f"Verifying action: {action_description}", extra={
                'action': action_description
            })

            # Determine verification type based on action description
            verification_type = self._determine_verification_type(action_description)

            # Perform verification based on type
            if verification_type == VerificationType.OBJECT_DETECTION:
                return await self._verify_object_detection(
                    action_description, before_image, after_image, parameters
                )
            elif verification_type == VerificationType.POSITION_CHANGE:
                return await self._verify_position_change(
                    action_description, before_image, after_image, parameters
                )
            elif verification_type == VerificationType.STATE_CHANGE:
                return await self._verify_state_change(
                    action_description, before_image, after_image, parameters
                )
            elif verification_type == VerificationType.COUNT_CHANGE:
                return await self._verify_count_change(
                    action_description, before_image, after_image, parameters
                )
            elif verification_type == VerificationType.SPATIAL_RELATION:
                return await self._verify_spatial_relation(
                    action_description, before_image, after_image, parameters
                )
            else:
                # Default to completion verification
                return await self._verify_completion(
                    action_description, before_image, after_image, parameters
                )

        except Exception as e:
            self.logger.error(f"Error in action verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.COMPLETION,
                description=f"Verification failed: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    def _determine_verification_type(self, action_description: str) -> VerificationType:
        """Determine the appropriate verification type based on action description"""
        action_lower = action_description.lower()

        if any(keyword in action_lower for keyword in ['grasp', 'pick', 'lift', 'hold']):
            return VerificationType.OBJECT_DETECTION
        elif any(keyword in action_lower for keyword in ['move', 'navigate', 'go to', 'position']):
            return VerificationType.POSITION_CHANGE
        elif any(keyword in action_lower for keyword in ['open', 'close', 'turn', 'switch']):
            return VerificationType.STATE_CHANGE
        elif any(keyword in action_lower for keyword in ['count', 'remove', 'add', 'collect']):
            return VerificationType.COUNT_CHANGE
        elif any(keyword in action_lower for keyword in ['left of', 'right of', 'near', 'beside']):
            return VerificationType.SPATIAL_RELATION
        else:
            return VerificationType.COMPLETION

    async def _verify_object_detection(self, action_description: str,
                                     before_image: np.ndarray,
                                     after_image: np.ndarray,
                                     parameters: Optional[Dict[str, Any]]) -> VerificationResult:
        """Verify object detection-related actions (e.g., grasping)"""
        try:
            target_object = parameters.get('target_object', '') if parameters else ''

            # Detect objects in both images
            before_objects = await self._detect_objects(before_image)
            after_objects = await self._detect_objects(after_image)

            # Check if target object is missing in after image (indicating successful grasp)
            target_missing = not any(
                target_object.lower() in obj['class'].lower() for obj in after_objects
            ) if target_object else False

            # Check if target object was present in before image
            target_present_before = any(
                target_object.lower() in obj['class'].lower() for obj in before_objects
            ) if target_object else True  # If no target specified, assume OK

            if target_present_before and target_missing:
                return VerificationResult(
                    status=VerificationStatus.SUCCESS,
                    confidence=0.9,
                    verification_type=VerificationType.OBJECT_DETECTION,
                    description=f"Successfully verified {action_description} - target object no longer visible",
                    timestamp=asyncio.get_event_loop().time()
                )
            elif not target_present_before:
                return VerificationResult(
                    status=VerificationStatus.FAILURE,
                    confidence=0.3,
                    verification_type=VerificationType.OBJECT_DETECTION,
                    description=f"Target object {target_object} not found before action",
                    timestamp=asyncio.get_event_loop().time()
                )
            else:
                return VerificationResult(
                    status=VerificationStatus.FAILURE,
                    confidence=0.2,
                    verification_type=VerificationType.OBJECT_DETECTION,
                    description=f"Target object still visible after grasp action",
                    timestamp=asyncio.get_event_loop().time()
                )

        except Exception as e:
            self.logger.error(f"Error in object detection verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.OBJECT_DETECTION,
                description=f"Object detection verification error: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    async def _verify_position_change(self, action_description: str,
                                    before_image: np.ndarray,
                                    after_image: np.ndarray,
                                    parameters: Optional[Dict[str, Any]]) -> VerificationResult:
        """Verify position change-related actions (e.g., navigation)"""
        try:
            # For position verification, we need to track specific objects
            # This is a simplified approach - in practice, you'd use visual odometry or landmarks
            before_features = self._extract_features(before_image)
            after_features = self._extract_features(after_image)

            # Calculate feature difference
            if before_features is not None and after_features is not None:
                # Calculate similarity (lower similarity indicates more change)
                similarity = self._calculate_feature_similarity(before_features, after_features)
                change_threshold = 0.7  # Adjust based on requirements

                if similarity < change_threshold:
                    return VerificationResult(
                        status=VerificationStatus.SUCCESS,
                        confidence=max(0.6, 1.0 - similarity),
                        verification_type=VerificationType.POSITION_CHANGE,
                        description=f"Position change verified - significant visual change detected",
                        timestamp=asyncio.get_event_loop().time()
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.FAILURE,
                        confidence=similarity,
                        verification_type=VerificationType.POSITION_CHANGE,
                        description=f"Position change not verified - insufficient visual change",
                        timestamp=asyncio.get_event_loop().time()
                    )
            else:
                return VerificationResult(
                    status=VerificationStatus.UNCERTAIN,
                    confidence=0.5,
                    verification_type=VerificationType.POSITION_CHANGE,
                    description="Unable to extract features for position verification",
                    timestamp=asyncio.get_event_loop().time()
                )

        except Exception as e:
            self.logger.error(f"Error in position change verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.POSITION_CHANGE,
                description=f"Position change verification error: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    async def _verify_state_change(self, action_description: str,
                                 before_image: np.ndarray,
                                 after_image: np.ndarray,
                                 parameters: Optional[Dict[str, Any]]) -> VerificationResult:
        """Verify state change-related actions (e.g., opening a door)"""
        try:
            # Calculate image differences to detect state changes
            if before_image.shape == after_image.shape:
                diff = cv2.absdiff(before_image, after_image)
                diff_magnitude = np.mean(diff)

                # Define threshold for significant change
                change_threshold = 10.0  # Adjust based on testing

                if diff_magnitude > change_threshold:
                    return VerificationResult(
                        status=VerificationStatus.SUCCESS,
                        confidence=min(0.9, diff_magnitude / 50.0),  # Normalize confidence
                        verification_type=VerificationType.STATE_CHANGE,
                        description=f"State change verified - significant visual difference detected ({diff_magnitude:.2f})",
                        timestamp=asyncio.get_event_loop().time()
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.FAILURE,
                        confidence=0.2,
                        verification_type=VerificationType.STATE_CHANGE,
                        description=f"State change not verified - insufficient visual difference ({diff_magnitude:.2f})",
                        timestamp=asyncio.get_event_loop().time()
                    )
            else:
                # Images have different shapes, can't compare directly
                return VerificationResult(
                    status=VerificationStatus.UNCERTAIN,
                    confidence=0.4,
                    verification_type=VerificationType.STATE_CHANGE,
                    description="Cannot compare images of different shapes",
                    timestamp=asyncio.get_event_loop().time()
                )

        except Exception as e:
            self.logger.error(f"Error in state change verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.STATE_CHANGE,
                description=f"State change verification error: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    async def _verify_count_change(self, action_description: str,
                                 before_image: np.ndarray,
                                 after_image: np.ndarray,
                                 parameters: Optional[Dict[str, Any]]) -> VerificationResult:
        """Verify count change-related actions (e.g., removing objects)"""
        try:
            before_objects = await self._detect_objects(before_image)
            after_objects = await self._detect_objects(after_image)

            before_count = len(before_objects)
            after_count = len(after_objects)

            # Determine expected change based on action
            expected_change = 0
            action_lower = action_description.lower()
            if 'remove' in action_lower or 'collect' in action_lower or 'take' in action_lower:
                expected_change = -1  # Expecting fewer objects
            elif 'add' in action_lower or 'place' in action_lower or 'put' in action_lower:
                expected_change = 1   # Expecting more objects

            actual_change = after_count - before_count
            change_matches = actual_change == expected_change

            if change_matches:
                confidence = 0.8 if abs(actual_change) > 0 else 0.6
                status = VerificationStatus.SUCCESS
                desc = f"Count change verified - objects changed from {before_count} to {after_count}"
            else:
                confidence = 0.3 if abs(actual_change) > 0 else 0.5
                status = VerificationStatus.FAILURE
                desc = f"Count change not verified - expected {expected_change:+d}, got {actual_change:+d}"

            return VerificationResult(
                status=status,
                confidence=confidence,
                verification_type=VerificationType.COUNT_CHANGE,
                description=desc,
                details={
                    'before_count': before_count,
                    'after_count': after_count,
                    'expected_change': expected_change,
                    'actual_change': actual_change
                },
                timestamp=asyncio.get_event_loop().time()
            )

        except Exception as e:
            self.logger.error(f"Error in count change verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.COUNT_CHANGE,
                description=f"Count change verification error: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    async def _verify_spatial_relation(self, action_description: str,
                                     before_image: np.ndarray,
                                     after_image: np.ndarray,
                                     parameters: Optional[Dict[str, Any]]) -> VerificationResult:
        """Verify spatial relation changes (e.g., moving object A near object B)"""
        try:
            # This is a complex verification that would require tracking specific objects
            # For now, we'll implement a simplified version
            before_objects = await self._detect_objects(before_image)
            after_objects = await self._detect_objects(after_image)

            # Check if spatial relationship keywords are mentioned in action
            action_lower = action_description.lower()
            has_spatial_keywords = any(keyword in action_lower for keyword in
                                     ['near', 'close to', 'next to', 'beside', 'left of', 'right of'])

            if has_spatial_keywords:
                # Calculate average change in object positions
                position_changes = []
                for before_obj in before_objects:
                    for after_obj in after_objects:
                        if before_obj['class'] == after_obj['class']:
                            # Calculate distance change
                            before_pos = before_obj.get('position_2d', (0, 0))
                            after_pos = after_obj.get('position_2d', (0, 0))
                            dist_before = math.sqrt(before_pos[0]**2 + before_pos[1]**2)
                            dist_after = math.sqrt(after_pos[0]**2 + after_pos[1]**2)
                            position_changes.append(abs(dist_after - dist_before))

                avg_change = np.mean(position_changes) if position_changes else 0

                if avg_change > 50:  # Threshold for significant movement
                    return VerificationResult(
                        status=VerificationStatus.SUCCESS,
                        confidence=min(0.9, avg_change / 100.0),
                        verification_type=VerificationType.SPATIAL_RELATION,
                        description=f"Spatial relation change verified - objects moved significantly",
                        timestamp=asyncio.get_event_loop().time()
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.FAILURE,
                        confidence=0.3,
                        verification_type=VerificationType.SPATIAL_RELATION,
                        description=f"Spatial relation change not verified - objects didn't move significantly",
                        timestamp=asyncio.get_event_loop().time()
                    )
            else:
                return VerificationResult(
                    status=VerificationStatus.UNCERTAIN,
                    confidence=0.5,
                    verification_type=VerificationType.SPATIAL_RELATION,
                    description="No spatial keywords detected in action description",
                    timestamp=asyncio.get_event_loop().time()
                )

        except Exception as e:
            self.logger.error(f"Error in spatial relation verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.SPATIAL_RELATION,
                description=f"Spatial relation verification error: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    async def _verify_completion(self, action_description: str,
                               before_image: np.ndarray,
                               after_image: np.ndarray,
                               parameters: Optional[Dict[str, Any]]) -> VerificationResult:
        """General completion verification"""
        try:
            # Perform general change detection
            if before_image.shape == after_image.shape:
                diff = cv2.absdiff(before_image, after_image)
                diff_magnitude = np.mean(diff)

                # Determine success based on change magnitude
                if diff_magnitude > 5.0:  # Significant change occurred
                    return VerificationResult(
                        status=VerificationStatus.SUCCESS,
                        confidence=min(0.9, diff_magnitude / 30.0),
                        verification_type=VerificationType.COMPLETION,
                        description=f"Action completion verified - visual change detected ({diff_magnitude:.2f})",
                        timestamp=asyncio.get_event_loop().time()
                    )
                else:
                    return VerificationResult(
                        status=VerificationStatus.FAILURE,
                        confidence=0.2,
                        verification_type=VerificationType.COMPLETION,
                        description=f"Action completion not verified - minimal visual change ({diff_magnitude:.2f})",
                        timestamp=asyncio.get_event_loop().time()
                    )
            else:
                return VerificationResult(
                    status=VerificationStatus.UNCERTAIN,
                    confidence=0.5,
                    verification_type=VerificationType.COMPLETION,
                    description="Cannot compare images of different shapes",
                    timestamp=asyncio.get_event_loop().time()
                )

        except Exception as e:
            self.logger.error(f"Error in completion verification: {e}")
            return VerificationResult(
                status=VerificationStatus.FAILURE,
                confidence=0.0,
                verification_type=VerificationType.COMPLETION,
                description=f"Completion verification error: {str(e)}",
                timestamp=asyncio.get_event_loop().time()
            )

    async def _detect_objects(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in an image (simplified implementation)"""
        try:
            # This is a simplified object detection
            # In a real implementation, you'd use a proper detection model
            if TORCH_AVAILABLE and self.object_detector is not None:
                # Convert numpy array to tensor format expected by model
                # This is a simplified approach
                pass

            # For now, use OpenCV to find contours as a basic object detection
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image

            # Apply some processing to identify potential objects
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            objects = []
            for i, contour in enumerate(contours[:10]):  # Limit to 10 largest contours
                if cv2.contourArea(contour) > 100:  # Filter small contours
                    x, y, w, h = cv2.boundingRect(contour)
                    center_x, center_y = x + w // 2, y + h // 2

                    objects.append({
                        'id': f'obj_{i}',
                        'class': 'object',  # Would be determined by actual detector
                        'position_2d': (center_x, center_y),
                        'bounding_box': (x, y, w, h),
                        'confidence': 0.5  # Default confidence
                    })

            return objects

        except Exception as e:
            self.logger.error(f"Error in object detection: {e}")
            return []

    def _extract_features(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Extract features from an image for comparison"""
        try:
            if self.feature_matcher is not None:
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                else:
                    gray = image

                # Detect and compute features
                kp, des = self.feature_matcher.detectAndCompute(gray, None)
                return des
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error extracting features: {e}")
            return None

    def _calculate_feature_similarity(self, features1: np.ndarray,
                                   features2: np.ndarray) -> float:
        """Calculate similarity between two feature sets"""
        try:
            if features1 is None or features2 is None:
                return 0.0

            if features1.size == 0 or features2.size == 0:
                return 0.0

            # Simple approach: calculate mean distance between features
            # In practice, you'd use a more sophisticated matching algorithm
            if features1.shape[1] == features2.shape[1]:  # Same feature dimension
                # For this example, we'll just compare the shapes and a simple metric
                diff = np.mean(np.abs(features1[:100] - features2[:100])) if min(len(features1), len(features2)) >= 100 else 0
                # Convert difference to similarity (0-1 scale, where 1 is most similar)
                similarity = max(0.0, 1.0 - diff / 1000.0)  # Adjust normalization as needed
                return similarity
            else:
                return 0.0

        except Exception as e:
            self.logger.error(f"Error calculating feature similarity: {e}")
            return 0.0

    async def verify_task_sequence(self, task_descriptions: List[str],
                                 image_sequence: List[np.ndarray]) -> List[VerificationResult]:
        """
        Verify a sequence of tasks by comparing consecutive images

        Args:
            task_descriptions: List of task descriptions
            image_sequence: List of images corresponding to each task state

        Returns:
            List of verification results for each task
        """
        if len(task_descriptions) != len(image_sequence) - 1:
            raise ValueError("Number of tasks must be one less than number of images")

        results = []
        for i, task_desc in enumerate(task_descriptions):
            before_img = image_sequence[i]
            after_img = image_sequence[i + 1]

            result = await self.verify_action_completion(task_desc, before_img, after_img)
            results.append(result)

        return results

    async def get_verification_confidence(self, action_result: VerificationResult,
                                        sensor_data: Optional[Dict[str, Any]] = None) -> float:
        """
        Adjust verification confidence based on additional sensor data
        """
        base_confidence = action_result.confidence

        if sensor_data:
            # Incorporate sensor data to adjust confidence
            # For example, if force sensors indicate grasp success, increase confidence
            if 'force_sensor' in sensor_data:
                force_reading = sensor_data['force_sensor']
                if force_reading > 5.0:  # Threshold for successful grasp
                    base_confidence = min(1.0, base_confidence + 0.2)

            # If joint position sensors indicate expected movement, increase confidence
            if 'joint_position' in sensor_data:
                joint_change = sensor_data['joint_position'].get('change', 0)
                if abs(joint_change) > 0.1:  # Significant joint movement
                    base_confidence = min(1.0, base_confidence + 0.1)

        return base_confidence


class VerificationReporter:
    """Generates reports from verification results"""

    @staticmethod
    def generate_task_report(results: List[VerificationResult]) -> str:
        """Generate a report for a sequence of verification results"""
        report_lines = ["Task Verification Report", "=" * 30]

        success_count = sum(1 for r in results if r.status == VerificationStatus.SUCCESS)
        total_count = len(results)

        report_lines.append(f"Total tasks: {total_count}")
        report_lines.append(f"Successful: {success_count}")
        report_lines.append(f"Success rate: {success_count/total_count*100:.1f}%")
        report_lines.append("")

        for i, result in enumerate(results, 1):
            status_symbol = {
                VerificationStatus.SUCCESS: "✓",
                VerificationStatus.FAILURE: "✗",
                VerificationStatus.UNCERTAIN: "?",
                VerificationStatus.IN_PROGRESS: "...",
                VerificationStatus.PENDING: "→"
            }.get(result.status, "?")

            report_lines.append(f"{i}. {status_symbol} {result.description}")
            report_lines.append(f"   Confidence: {result.confidence:.2f}")
            report_lines.append(f"   Type: {result.verification_type.value}")
            report_lines.append("")

        return "\n".join(report_lines)

    @staticmethod
    def generate_summary(results: List[VerificationResult]) -> Dict[str, Any]:
        """Generate a summary of verification results"""
        summary = {
            'total_verifications': len(results),
            'success_count': 0,
            'failure_count': 0,
            'uncertain_count': 0,
            'average_confidence': 0.0,
            'success_rate': 0.0
        }

        for result in results:
            if result.status == VerificationStatus.SUCCESS:
                summary['success_count'] += 1
            elif result.status == VerificationStatus.FAILURE:
                summary['failure_count'] += 1
            elif result.status == VerificationStatus.UNCERTAIN:
                summary['uncertain_count'] += 1

        if results:
            summary['average_confidence'] = sum(r.confidence for r in results) / len(results)
            summary['success_rate'] = summary['success_count'] / len(results)

        return summary


# Example usage and testing
async def test_visual_verification():
    """Test the visual verification system"""
    print("Testing Visual Verification System")
    print("=" * 40)

    verifier = VisualVerificationSystem()

    if not verifier.init_success:
        print("Warning: Verification system not fully initialized, using basic functionality")

    # Create dummy images for testing (in practice, these would come from a camera)
    import numpy as np
    before_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    after_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Test 1: Object detection verification
    print("\n1. Testing object detection verification...")
    result1 = await verifier.verify_action_completion(
        "grasp the red cup",
        before_image,
        after_image,
        {"target_object": "cup"}
    )
    print(f"   Status: {result1.status.value}, Confidence: {result1.confidence:.2f}")
    print(f"   Description: {result1.description}")

    # Test 2: Position change verification
    print("\n2. Testing position change verification...")
    result2 = await verifier.verify_action_completion(
        "navigate to the kitchen",
        before_image,
        after_image
    )
    print(f"   Status: {result2.status.value}, Confidence: {result2.confidence:.2f}")
    print(f"   Description: {result2.description}")

    # Test 3: State change verification
    print("\n3. Testing state change verification...")
    result3 = await verifier.verify_action_completion(
        "open the door",
        before_image,
        after_image
    )
    print(f"   Status: {result3.status.value}, Confidence: {result3.confidence:.2f}")
    print(f"   Description: {result3.description}")

    # Test 4: Count change verification
    print("\n4. Testing count change verification...")
    result4 = await verifier.verify_action_completion(
        "remove the book from the table",
        before_image,
        after_image
    )
    print(f"   Status: {result4.status.value}, Confidence: {result4.confidence:.2f}")
    print(f"   Description: {result4.description}")

    # Generate summary
    print("\n5. Verification Summary:")
    results = [result1, result2, result3, result4]
    summary = VerificationReporter.generate_summary(results)
    print(f"   Success rate: {summary['success_rate']:.2%}")
    print(f"   Average confidence: {summary['average_confidence']:.2f}")
    print(f"   Total verifications: {summary['total_verifications']}")

    # Generate detailed report
    print("\n6. Detailed Report:")
    report = VerificationReporter.generate_task_report(results)
    print(report)

    print("\nVisual verification system test completed!")


if __name__ == "__main__":
    asyncio.run(test_visual_verification())