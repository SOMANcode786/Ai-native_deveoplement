"""
Language Grounding Examples for Vision-Language-Action (VLA) System

This module demonstrates how language references are grounded to visual objects
in the VLA system, enabling the robot to understand and act upon language commands
that reference physical objects.
"""

import asyncio
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Import our VLA system components
from src.vision_language.grounding import VisionLanguageGrounding, GroundingResult, GroundingMethod
from src.vision_language.object_detection import ObjectDetectionManager, DetectionResult
from src.error_handling import ErrorHandler, VLALogger


@dataclass
class GroundingExample:
    """Represents a language grounding example"""
    language_query: str
    expected_object_class: str
    scenario_description: str
    environment_context: Dict[str, Any]


class LanguageGroundingExamples:
    """
    Examples and demonstrations of language grounding in the VLA system
    """

    def __init__(self):
        self.logger = VLALogger("LanguageGroundingExamples")
        self.error_handler = ErrorHandler(self.logger)
        self.grounding_system = VisionLanguageGrounding(method=GroundingMethod.HYBRID)
        self.detection_manager = ObjectDetectionManager()

        self.examples = self._create_examples()

    def _create_examples(self) -> List[GroundingExample]:
        """Create a set of language grounding examples"""
        return [
            GroundingExample(
                language_query="the red cup on the table",
                expected_object_class="cup",
                scenario_description="Basic object identification with color and location",
                environment_context={
                    "objects": [
                        {"id": "cup_1", "class": "cup", "color": "red", "position": (1.0, 2.0, 0.0)},
                        {"id": "book_1", "class": "book", "color": "blue", "position": (1.5, 2.0, 0.0)},
                        {"id": "table_1", "class": "table", "position": (1.0, 2.0, 0.0)}
                    ]
                }
            ),
            GroundingExample(
                language_query="the book to the left of the laptop",
                expected_object_class="book",
                scenario_description="Spatial relationship grounding",
                environment_context={
                    "objects": [
                        {"id": "laptop_1", "class": "laptop", "position": (1.0, 1.0, 0.0)},
                        {"id": "book_1", "class": "book", "position": (0.5, 1.0, 0.0)},  # To the left
                        {"id": "book_2", "class": "book", "position": (1.5, 1.0, 0.0)}   # To the right
                    ]
                }
            ),
            GroundingExample(
                language_query="pick up the largest object",
                expected_object_class="object",
                scenario_description="Attribute-based selection",
                environment_context={
                    "objects": [
                        {"id": "small_ball", "class": "ball", "size": 0.1, "position": (1.0, 1.0, 0.0)},
                        {"id": "medium_box", "class": "box", "size": 0.3, "position": (1.5, 1.0, 0.0)},
                        {"id": "large_crate", "class": "crate", "size": 0.8, "position": (2.0, 1.0, 0.0)}
                    ]
                }
            ),
            GroundingExample(
                language_query="the cup near the window",
                expected_object_class="cup",
                scenario_description="Proximity-based grounding",
                environment_context={
                    "objects": [
                        {"id": "cup_1", "class": "cup", "position": (0.5, 0.5, 0.0)},  # Near window
                        {"id": "cup_2", "class": "cup", "position": (5.0, 5.0, 0.0)},  # Far from window
                        {"id": "window_1", "class": "window", "position": (0.0, 0.0, 0.0)}
                    ]
                }
            )
        ]

    async def demonstrate_grounding_process(self, example: GroundingExample) -> Dict[str, Any]:
        """
        Demonstrate the complete grounding process for an example
        """
        try:
            self.logger.info(f"Grounding query: {example.language_query}",
                           component="LanguageGroundingExamples")

            # Create a simulated image with the environment context
            simulated_image = self._create_simulated_image(example.environment_context)

            # Perform object detection on the simulated image
            detections = await self.detection_manager.detect_objects(simulated_image)

            # Perform language grounding
            grounding_results = await self.grounding_system.ground_language_reference(
                simulated_image,
                example.language_query,
                candidate_objects=self._convert_to_candidate_format(detections)
            )

            self.logger.info(f"Found {len(grounding_results)} grounding matches",
                           component="LanguageGroundingExamples")

            # Process results
            results = {
                "success": len(grounding_results) > 0,
                "query": example.language_query,
                "expected_class": example.expected_object_class,
                "grounding_results": [
                    {
                        "object_id": result.object_id,
                        "object_class": result.object_class,
                        "confidence": result.confidence,
                        "position_2d": result.position_2d,
                        "position_3d": result.position_3d,
                        "bounding_box": result.bounding_box
                    }
                    for result in grounding_results
                ],
                "example_description": example.scenario_description,
                "environment_context": example.environment_context
            }

            return results

        except Exception as e:
            self.error_handler.handle_exception(e, "LanguageGroundingExamples.demonstrate_grounding_process")
            return {
                "success": False,
                "error": str(e),
                "query": example.language_query
            }

    def _create_simulated_image(self, env_context: Dict[str, Any]) -> np.ndarray:
        """
        Create a simulated image based on environment context
        In a real system, this would come from a camera
        """
        # Create a dummy image (in practice, this would be from a real camera)
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # Add some simple shapes to represent objects
        if env_context.get("objects"):
            for i, obj in enumerate(env_context["objects"]):
                # Draw a rectangle representing the object
                x = int(obj.get("position", (0, 0, 0))[0] * 100) % 600
                y = int(obj.get("position", (0, 0, 0))[1] * 100) % 400
                color = tuple(np.random.randint(0, 255, 3).tolist())
                cv2 = None
                try:
                    import cv2
                    cv2.rectangle(image, (x, y), (x + 50, y + 50), color, -1)
                except ImportError:
                    # If OpenCV is not available, just return the random image
                    pass

        return image

    def _convert_to_candidate_format(self, detections: List[DetectionResult]) -> List[Dict[str, Any]]:
        """
        Convert DetectionResult objects to the format expected by grounding system
        """
        candidates = []
        for detection in detections:
            candidate = {
                'id': detection.object_id,
                'class': detection.class_name,
                'position_2d': detection.position_2d,
                'bounding_box': detection.bounding_box,
                'confidence': detection.confidence
            }
            candidates.append(candidate)
        return candidates

    async def run_all_examples(self) -> List[Dict[str, Any]]:
        """
        Run all language grounding examples and return results
        """
        results = []

        for i, example in enumerate(self.examples):
            self.logger.info(f"Running grounding example {i+1}: {example.scenario_description}",
                           component="LanguageGroundingExamples")

            result = await self.demonstrate_grounding_process(example)
            results.append(result)

        return results

    def evaluate_grounding_accuracy(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate the accuracy of grounding results
        """
        total_examples = len(results)
        successful_groundings = sum(1 for result in results if result["success"])

        # For this example, we'll consider it correct if the expected class is in the results
        correct_class_groundings = 0
        for result in results:
            if result["success"]:
                for grounding in result["grounding_results"]:
                    if grounding["object_class"].lower() == result["expected_class"].lower():
                        correct_class_groundings += 1
                        break

        accuracy = correct_class_groundings / total_examples if total_examples > 0 else 0

        evaluation = {
            "total_examples": total_examples,
            "successful_groundings": successful_groundings,
            "correct_class_groundings": correct_class_groundings,
            "accuracy": accuracy,
            "success_rate": successful_groundings / total_examples if total_examples > 0 else 0
        }

        return evaluation

    async def demonstrate_spatial_grounding(self) -> Dict[str, Any]:
        """
        Demonstrate spatial relationship grounding
        """
        try:
            # Create a simulated image with spatial relationships
            env_context = {
                "objects": [
                    {"id": "laptop_1", "class": "laptop", "position": (1.0, 1.0, 0.0)},
                    {"id": "book_1", "class": "book", "position": (0.5, 1.0, 0.0)},  # To the left
                    {"id": "pen_1", "class": "pen", "position": (1.5, 1.0, 0.0)},   # To the right
                    {"id": "cup_1", "class": "cup", "position": (1.0, 0.5, 0.0)}    # Below
                ]
            }

            simulated_image = self._create_simulated_image(env_context)
            detections = await self.detection_manager.detect_objects(simulated_image)

            # Test spatial grounding: "the book to the left of the laptop"
            spatial_result = await self.grounding_system.ground_spatial_reference(
                simulated_image,
                "book",
                "laptop",
                "to the left of"
            )

            result = {
                "success": spatial_result is not None,
                "query_type": "spatial_relationship",
                "description": "Book to the left of laptop",
                "found_object": spatial_result.object_class if spatial_result else None,
                "confidence": spatial_result.confidence if spatial_result else 0.0,
                "position_2d": spatial_result.position_2d if spatial_result else None
            }

            return result

        except Exception as e:
            self.error_handler.handle_exception(e, "LanguageGroundingExamples.demonstrate_spatial_grounding")
            return {
                "success": False,
                "error": str(e),
                "query_type": "spatial_relationship"
            }

    async def demonstrate_contextual_grounding(self) -> Dict[str, Any]:
        """
        Demonstrate grounding with context awareness
        """
        try:
            # Create a simulated image with multiple similar objects
            env_context = {
                "objects": [
                    {"id": "cup_1", "class": "cup", "color": "red", "position": (1.0, 1.0, 0.0)},
                    {"id": "cup_2", "class": "cup", "color": "blue", "position": (2.0, 1.0, 0.0)},
                    {"id": "cup_3", "class": "cup", "color": "red", "position": (1.5, 2.0, 0.0)}
                ],
                "robot_position": (0.0, 0.0, 0.0),
                "user_position": (3.0, 3.0, 0.0)
            }

            simulated_image = self._create_simulated_image(env_context)
            detections = await self.detection_manager.detect_objects(simulated_image)

            # Test contextual grounding: "the red cup closest to me"
            # This would require additional context processing
            grounding_results = await self.grounding_system.ground_language_reference(
                simulated_image,
                "the red cup",
                candidate_objects=self._convert_to_candidate_format(detections)
            )

            # Filter by color (red) and rank by proximity to user
            red_cup_results = [
                result for result in grounding_results
                if "red" in result.object_id.lower() or "red" in result.object_class.lower()
            ]

            result = {
                "success": len(red_cup_results) > 0,
                "query_type": "contextual",
                "description": "Red cups in the scene",
                "found_objects": [r.object_class for r in red_cup_results],
                "confidences": [r.confidence for r in red_cup_results],
                "total_red_cups": len(red_cup_results)
            }

            return result

        except Exception as e:
            self.error_handler.handle_exception(e, "LanguageGroundingExamples.demonstrate_contextual_grounding")
            return {
                "success": False,
                "error": str(e),
                "query_type": "contextual"
            }


async def run_language_grounding_examples():
    """
    Run the language grounding examples
    """
    print("Language Grounding Examples for VLA System")
    print("=" * 60)

    examples = LanguageGroundingExamples()

    print(f"\nLoaded {len(examples.examples)} language grounding examples:")
    for i, example in enumerate(examples.examples, 1):
        print(f"  {i}. {example.scenario_description}")
        print(f"     Query: '{example.language_query}'")

    print(f"\nRunning grounding process for all examples...")

    results = await examples.run_all_examples()

    print(f"\nGrounding Results:")
    for i, result in enumerate(results, 1):
        status = "✓ SUCCESS" if result["success"] else "✗ FAILED"
        print(f"  Example {i}: {status}")
        if result["success"]:
            print(f"    Query: {result['query']}")
            print(f"    Found: {len(result['grounding_results'])} objects")
            for j, obj in enumerate(result['grounding_results'][:2]):  # Show first 2
                print(f"      {j+1}. {obj['object_class']} (confidence: {obj['confidence']:.2f})")
            if len(result['grounding_results']) > 2:
                print(f"      ... and {len(result['grounding_results']) - 2} more")
        else:
            print(f"    Error: {result['error']}")

    # Evaluate accuracy
    evaluation = examples.evaluate_grounding_accuracy(results)
    print(f"\nAccuracy Evaluation:")
    print(f"  Total examples: {evaluation['total_examples']}")
    print(f"  Successful groundings: {evaluation['successful_groundings']}")
    print(f"  Correct class groundings: {evaluation['correct_class_groundings']}")
    print(f"  Accuracy: {evaluation['accuracy']:.2%}")
    print(f"  Success rate: {evaluation['success_rate']:.2%}")

    # Demonstrate spatial grounding
    print(f"\nDemonstrating spatial relationship grounding:")
    spatial_result = await examples.demonstrate_spatial_grounding()
    if spatial_result["success"]:
        print(f"  ✓ Found {spatial_result['found_object']} with confidence {spatial_result['confidence']:.2f}")
    else:
        print(f"  ✗ Spatial grounding failed: {spatial_result.get('error', 'Unknown error')}")

    # Demonstrate contextual grounding
    print(f"\nDemonstrating contextual grounding:")
    context_result = await examples.demonstrate_contextual_grounding()
    if context_result["success"]:
        print(f"  ✓ Found {context_result['total_red_cups']} red cups")
        print(f"  Confidences: {[f'{c:.2f}' for c in context_result['confidences']]}")
    else:
        print(f"  ✗ Contextual grounding failed: {context_result.get('error', 'Unknown error')}")

    print(f"\nLanguage grounding examples completed successfully!")


def explain_grounding_techniques():
    """
    Explain the different grounding techniques used in the VLA system
    """
    print("\nLanguage Grounding Techniques in VLA System")
    print("=" * 50)

    techniques = {
        "CLIP-Based Grounding": {
            "description": "Uses Contrastive Language-Image Pretraining models to match language descriptions with visual features",
            "advantages": ["Robust to novel object categories", "Good generalization", "Handles abstract descriptions"],
            "challenges": ["Computationally expensive", "Requires large models", "May miss fine details"]
        },
        "Object Detection Grounding": {
            "description": "Uses object detection models to identify objects and matches them with language queries using keyword matching",
            "advantages": ["Fast processing", "Accurate bounding boxes", "Good for known categories"],
            "challenges": ["Limited to trained categories", "Simple matching approach", "Less contextual"]
        },
        "Hybrid Approach": {
            "description": "Combines multiple grounding methods for improved accuracy and robustness",
            "advantages": ["Best of both approaches", "More robust", "Handles various query types"],
            "challenges": ["More complex", "Higher computational cost", "Requires careful integration"]
        },
        "Spatial Grounding": {
            "description": "Understands spatial relationships like 'left of', 'near', 'between' for precise object identification",
            "advantages": ["Precise object identification", "Handles ambiguous queries", "Context-aware"],
            "challenges": ["Requires accurate position data", "Complex spatial reasoning", "Dependent on detection quality"]
        }
    }

    for technique, info in techniques.items():
        print(f"\n{technique}:")
        print(f"  Description: {info['description']}")
        print(f"  Advantages: {', '.join(info['advantages'])}")
        print(f"  Challenges: {', '.join(info['challenges'])}")


if __name__ == "__main__":
    # Run the language grounding examples
    asyncio.run(run_language_grounding_examples())

    # Explain grounding techniques
    explain_grounding_techniques()