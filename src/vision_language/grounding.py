"""
Vision-Language Grounding Module for Vision-Language-Action (VLA) System

This module provides functionality for connecting language references to visual objects,
enabling the robot to understand and act upon language commands that reference physical objects.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    from transformers import CLIPProcessor, CLIPModel
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    CLIPProcessor = None
    CLIPModel = None


class GroundingMethod(Enum):
    """Methods for vision-language grounding"""
    CLIP_BASED = "clip_based"
    OBJECT_DETECTION = "object_detection"
    SEMANTIC_SEGMENTATION = "semantic_segmentation"
    HYBRID = "hybrid"


@dataclass
class GroundingResult:
    """Result of vision-language grounding"""
    object_id: str
    object_class: str
    confidence: float
    position_3d: Optional[Tuple[float, float, float]]
    position_2d: Optional[Tuple[int, int]]  # (x, y) in image coordinates
    bounding_box: Optional[Tuple[int, int, int, int]]  # (x, y, width, height)
    language_query: str
    grounding_method: GroundingMethod


class VisionLanguageGrounding:
    """
    Core class for vision-language grounding
    Connects linguistic references to physical objects in the environment
    """

    def __init__(self, method: GroundingMethod = GroundingMethod.HYBRID):
        self.method = method
        self.logger = logging.getLogger(__name__)
        self.clip_model = None
        self.clip_processor = None

        # Initialize the grounding method
        if method in [GroundingMethod.CLIP_BASED, GroundingMethod.HYBRID] and CLIP_AVAILABLE:
            try:
                self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                self.logger.info("CLIP model loaded for grounding")
            except Exception as e:
                self.logger.warning(f"Failed to load CLIP model: {e}")
                self.method = GroundingMethod.OBJECT_DETECTION

    async def ground_language_reference(self, image: np.ndarray,
                                      language_query: str,
                                      candidate_objects: Optional[List[Dict[str, Any]]] = None,
                                      camera_intrinsics: Optional[Dict[str, Any]] = None) -> List[GroundingResult]:
        """
        Ground a language reference to objects in the image

        Args:
            image: Input image as numpy array
            language_query: Natural language description of the target object
            candidate_objects: Optional list of pre-detected objects to ground against
            camera_intrinsics: Camera intrinsic parameters for 3D position calculation

        Returns:
            List of grounding results ranked by confidence
        """
        try:
            if self.method == GroundingMethod.CLIP_BASED:
                return await self._clip_based_grounding(image, language_query, candidate_objects, camera_intrinsics)
            elif self.method == GroundingMethod.OBJECT_DETECTION:
                return await self._object_detection_grounding(image, language_query, camera_intrinsics)
            elif self.method == GroundingMethod.HYBRID:
                return await self._hybrid_grounding(image, language_query, candidate_objects, camera_intrinsics)
            else:
                raise ValueError(f"Unknown grounding method: {self.method}")

        except Exception as e:
            self.logger.error(f"Error in vision-language grounding: {e}")
            return []

    async def _clip_based_grounding(self, image: np.ndarray,
                                  language_query: str,
                                  candidate_objects: Optional[List[Dict[str, Any]]],
                                  camera_intrinsics: Optional[Dict[str, Any]]) -> List[GroundingResult]:
        """Ground language using CLIP-based approach"""
        if not CLIP_AVAILABLE or self.clip_model is None:
            self.logger.error("CLIP not available for grounding")
            return []

        try:
            # If candidate objects are provided, use them for grounding
            if candidate_objects:
                results = []
                for obj in candidate_objects:
                    # Calculate similarity between object and language query
                    object_description = f"{obj.get('class', 'object')} {obj.get('color', '')}".strip()

                    # Use CLIP to calculate similarity
                    inputs = self.clip_processor(
                        text=[language_query, object_description],
                        images=[image],
                        return_tensors="pt",
                        padding=True
                    )

                    outputs = self.clip_model(**inputs)
                    logits_per_image = outputs.logits_per_image
                    probs = logits_per_image.softmax(dim=1)

                    # Get similarity score
                    similarity = probs[0][0].item()  # Score for the language query vs image

                    results.append(GroundingResult(
                        object_id=obj.get('id', 'unknown'),
                        object_class=obj.get('class', 'unknown'),
                        confidence=similarity,
                        position_3d=obj.get('position_3d'),
                        position_2d=obj.get('position_2d'),
                        bounding_box=obj.get('bounding_box'),
                        language_query=language_query,
                        grounding_method=GroundingMethod.CLIP_BASED
                    ))

                # Sort by confidence
                results.sort(key=lambda x: x.confidence, reverse=True)
                return results
            else:
                # If no candidates, we need to detect objects first
                # This is a simplified approach - in practice, you'd want to detect objects
                # and then use CLIP to match them to the query
                detected_objects = await self._detect_objects_basic(image)

                results = []
                for obj in detected_objects:
                    # Create text descriptions for CLIP
                    text_descriptions = [
                        language_query,
                        f"{obj['class']} in the image",
                        f"{obj['class']} object"
                    ]

                    inputs = self.clip_processor(
                        text=text_descriptions,
                        images=[image],
                        return_tensors="pt",
                        padding=True
                    )

                    outputs = self.clip_model(**inputs)
                    logits_per_image = outputs.logits_per_image
                    probs = logits_per_image.softmax(dim=1)

                    # Use the probability for the language query as confidence
                    confidence = probs[0][0].item()

                    results.append(GroundingResult(
                        object_id=obj.get('id', f"obj_{len(results)}"),
                        object_class=obj['class'],
                        confidence=confidence,
                        position_3d=obj.get('position_3d'),
                        position_2d=obj.get('position_2d'),
                        bounding_box=obj['bounding_box'],
                        language_query=language_query,
                        grounding_method=GroundingMethod.CLIP_BASED
                    ))

                # Sort by confidence
                results.sort(key=lambda x: x.confidence, reverse=True)
                return results

        except Exception as e:
            self.logger.error(f"Error in CLIP-based grounding: {e}")
            return []

    async def _object_detection_grounding(self, image: np.ndarray,
                                        language_query: str,
                                        camera_intrinsics: Optional[Dict[str, Any]]) -> List[GroundingResult]:
        """Ground language using object detection approach"""
        try:
            # Detect objects in the image
            detected_objects = await self._detect_objects_basic(image)

            # Simple keyword matching between query and object classes
            results = []
            for obj in detected_objects:
                confidence = self._calculate_keyword_match(obj['class'], language_query)

                results.append(GroundingResult(
                    object_id=obj.get('id', f"obj_{len(results)}"),
                    object_class=obj['class'],
                    confidence=confidence,
                    position_3d=obj.get('position_3d'),
                    position_2d=obj.get('position_2d'),
                    bounding_box=obj['bounding_box'],
                    language_query=language_query,
                    grounding_method=GroundingMethod.OBJECT_DETECTION
                ))

            # Sort by confidence
            results.sort(key=lambda x: x.confidence, reverse=True)
            return results

        except Exception as e:
            self.logger.error(f"Error in object detection grounding: {e}")
            return []

    async def _hybrid_grounding(self, image: np.ndarray,
                              language_query: str,
                              candidate_objects: Optional[List[Dict[str, Any]]],
                              camera_intrinsics: Optional[Dict[str, Any]]) -> List[GroundingResult]:
        """Combine multiple grounding approaches for better accuracy"""
        try:
            # Get results from object detection
            detection_results = await self._object_detection_grounding(image, language_query, camera_intrinsics)

            # If we have CLIP available, also get CLIP-based results
            clip_results = []
            if CLIP_AVAILABLE and self.clip_model is not None:
                clip_results = await self._clip_based_grounding(image, language_query, candidate_objects, camera_intrinsics)

            # Combine and re-rank results
            combined_results = self._combine_grounding_results(detection_results, clip_results)

            return combined_results

        except Exception as e:
            self.logger.error(f"Error in hybrid grounding: {e}")
            # Fallback to object detection only
            return await self._object_detection_grounding(image, language_query, camera_intrinsics)

    def _combine_grounding_results(self, detection_results: List[GroundingResult],
                                 clip_results: List[GroundingResult]) -> List[GroundingResult]:
        """Combine results from different grounding methods"""
        # Create a mapping from object_id to all results for that object
        result_map: Dict[str, List[GroundingResult]] = {}

        for result in detection_results:
            if result.object_id not in result_map:
                result_map[result.object_id] = []
            result_map[result.object_id].append(result)

        for result in clip_results:
            if result.object_id not in result_map:
                result_map[result.object_id] = []
            result_map[result.object_id].append(result)

        # Combine confidence scores for each object
        combined_results = []
        for obj_id, results in result_map.items():
            # Average the confidence scores
            avg_confidence = sum(r.confidence for r in results) / len(results)

            # Use the first result as template and update confidence
            primary_result = results[0]
            combined_result = GroundingResult(
                object_id=primary_result.object_id,
                object_class=primary_result.object_class,
                confidence=avg_confidence,
                position_3d=primary_result.position_3d,
                position_2d=primary_result.position_2d,
                bounding_box=primary_result.bounding_box,
                language_query=primary_result.language_query,
                grounding_method=GroundingMethod.HYBRID
            )
            combined_results.append(combined_result)

        # Sort by combined confidence
        combined_results.sort(key=lambda x: x.confidence, reverse=True)
        return combined_results

    async def _detect_objects_basic(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Basic object detection (placeholder implementation)"""
        if not OPENCV_AVAILABLE:
            # Return some dummy objects
            return [
                {
                    'id': 'object_1',
                    'class': 'object',
                    'position_2d': (100, 100),
                    'bounding_box': (90, 90, 50, 50)
                }
            ]

        try:
            # Convert image if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image

            # Simple contour detection as placeholder
            # In a real implementation, you'd use a proper object detection model
            contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            objects = []
            for i, contour in enumerate(contours[:5]):  # Limit to first 5 contours
                x, y, w, h = cv2.boundingRect(contour)

                # Calculate center
                center_x, center_y = x + w // 2, y + h // 2

                objects.append({
                    'id': f'obj_{i}',
                    'class': 'object',  # Would be determined by actual detector
                    'position_2d': (center_x, center_y),
                    'bounding_box': (x, y, w, h)
                })

            return objects
        except Exception as e:
            self.logger.error(f"Error in basic object detection: {e}")
            return []

    def _calculate_keyword_match(self, object_class: str, language_query: str) -> float:
        """Calculate similarity between object class and language query"""
        object_lower = object_class.lower()
        query_lower = language_query.lower()

        # Simple keyword matching
        if object_lower in query_lower or query_lower in object_lower:
            return 0.9  # High confidence for exact match

        # Partial matches
        query_words = query_lower.split()
        object_words = object_lower.split()

        matches = sum(1 for word in query_words if word in object_words)
        if matches > 0:
            return 0.7  # Medium confidence for partial match

        return 0.1  # Low confidence for no match

    async def ground_spatial_reference(self, image: np.ndarray,
                                     language_query: str,
                                     reference_object: str,
                                     spatial_relation: str) -> Optional[GroundingResult]:
        """
        Ground spatial references like "the cup to the left of the book"
        """
        try:
            # First, ground the reference object
            reference_results = await self.ground_language_reference(
                image, reference_object
            )

            if not reference_results:
                return None

            reference_obj = reference_results[0]  # Use the highest confidence

            # Then find objects matching the main query near the reference object
            all_results = await self.ground_language_reference(image, language_query)

            # Filter results based on spatial relationship
            spatially_filtered = self._apply_spatial_filter(
                all_results, reference_obj, spatial_relation
            )

            if spatially_filtered:
                return spatially_filtered[0]  # Return highest confidence
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error in spatial grounding: {e}")
            return None

    def _apply_spatial_filter(self, candidate_objects: List[GroundingResult],
                            reference_object: GroundingResult,
                            spatial_relation: str) -> List[GroundingResult]:
        """Apply spatial filtering based on relationship"""
        if not reference_object.position_2d:
            return candidate_objects  # Can't apply spatial filter without position

        ref_x, ref_y = reference_object.position_2d
        filtered = []

        for obj in candidate_objects:
            if not obj.position_2d:
                continue

            obj_x, obj_y = obj.position_2d

            # Apply spatial relationship filter
            if spatial_relation.lower() == "left of" and obj_x < ref_x:
                filtered.append(obj)
            elif spatial_relation.lower() == "right of" and obj_x > ref_x:
                filtered.append(obj)
            elif spatial_relation.lower() == "above" and obj_y < ref_y:
                filtered.append(obj)
            elif spatial_relation.lower() == "below" and obj_y > ref_y:
                filtered.append(obj)
            elif spatial_relation.lower() == "near" and self._is_near(obj_x, obj_y, ref_x, ref_y):
                filtered.append(obj)

        return filtered

    def _is_near(self, x1: int, y1: int, x2: int, y2: int, threshold: int = 100) -> bool:
        """Check if two points are near each other"""
        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return distance <= threshold


class GroundingValidator:
    """Validates grounding results for safety and feasibility"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_grounding_result(self, result: GroundingResult,
                                workspace_limits: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Validate a grounding result for safety and feasibility
        """
        validation = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'confidence_ok': True
        }

        # Check confidence threshold
        if result.confidence < 0.3:
            validation['confidence_ok'] = False
            validation['warnings'].append(f"Low confidence: {result.confidence:.2f}")

        # Check if position is valid
        if result.position_3d:
            x, y, z = result.position_3d
            if workspace_limits:
                if (x < workspace_limits.get('min_x', float('-inf')) or
                    x > workspace_limits.get('max_x', float('inf')) or
                    y < workspace_limits.get('min_y', float('-inf')) or
                    y > workspace_limits.get('max_y', float('inf')) or
                    z < workspace_limits.get('min_z', float('-inf')) or
                    z > workspace_limits.get('max_z', float('inf'))):
                    validation['valid'] = False
                    validation['errors'].append(f"Object outside workspace: ({x}, {y}, {z})")

        return validation


# Example usage and testing
async def test_vision_language_grounding():
    """Test the vision-language grounding functionality"""
    print("Testing Vision-Language Grounding")
    print("=" * 40)

    # Create grounding instance
    grounding = VisionLanguageGrounding(method=GroundingMethod.OBJECT_DETECTION)

    # Simulate an image (in practice, this would come from a camera)
    if OPENCV_AVAILABLE:
        import numpy as np
        # Create a dummy image for testing
        dummy_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    else:
        # Create a simple array
        dummy_image = np.random.random((100, 100, 3))

    # Test grounding a simple object
    print("\n1. Testing object grounding...")
    results = await grounding.ground_language_reference(
        dummy_image,
        "the red cup"
    )

    print(f"   Found {len(results)} potential matches")
    for i, result in enumerate(results[:3]):  # Show top 3
        print(f"   {i+1}. {result.object_class} with confidence {result.confidence:.2f}")

    # Test spatial grounding
    print("\n2. Testing spatial grounding...")
    spatial_result = await grounding.ground_spatial_reference(
        dummy_image,
        "cup",
        "book",
        "to the left of"
    )

    if spatial_result:
        print(f"   Found spatial relationship: {spatial_result.object_class}")
    else:
        print("   No spatial relationship found (expected with dummy image)")

    # Test with candidate objects
    print("\n3. Testing with candidate objects...")
    candidate_objects = [
        {
            'id': 'cup_1',
            'class': 'cup',
            'color': 'red',
            'position_2d': (100, 100),
            'bounding_box': (90, 90, 50, 50)
        },
        {
            'id': 'book_1',
            'class': 'book',
            'color': 'blue',
            'position_2d': (200, 150),
            'bounding_box': (180, 140, 80, 60)
        }
    ]

    results_with_candidates = await grounding.ground_language_reference(
        dummy_image,
        "the red cup",
        candidate_objects=candidate_objects
    )

    print(f"   Found {len(results_with_candidates)} matches with candidates")
    for i, result in enumerate(results_with_candidates):
        print(f"   {i+1}. {result.object_class} (ID: {result.object_id}) with confidence {result.confidence:.2f}")

    print("\nVision-language grounding test completed!")


if __name__ == "__main__":
    asyncio.run(test_vision_language_grounding())