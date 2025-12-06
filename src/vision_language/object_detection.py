"""
Object Detection Integration for Vision-Language-Action (VLA) System

This module provides object detection capabilities that integrate with the
vision-language grounding system for the VLA framework.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
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
    from torchvision.models.detection import fasterrcnn_resnet50_fpn, ssd300_vgg16, maskrcnn_resnet50_fpn
    from torchvision.transforms import functional as F
    TORCHVISION_AVAILABLE = True
except ImportError:
    TORCHVISION_AVAILABLE = False
    fasterrcnn_resnet50_fpn = None
    ssd300_vgg16 = None
    maskrcnn_resnet50_fpn = None
    F = None


class DetectionModelType(Enum):
    """Types of object detection models supported"""
    FASTER_RCNN = "faster_rcnn"
    SSD = "ssd"
    MASK_RCNN = "mask_rcnn"
    YOLO = "yolo"  # Placeholder - would need separate integration
    CUSTOM = "custom"


@dataclass
class DetectionResult:
    """Result of object detection"""
    object_id: str
    class_name: str
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # (x, y, width, height)
    position_2d: Tuple[int, int]  # Center of bounding box
    segmentation_mask: Optional[np.ndarray] = None  # For instance segmentation
    features: Optional[np.ndarray] = None  # Feature vector for similarity matching


class ObjectDetectionManager:
    """
    Manager class for object detection in the VLA system
    Handles model loading, inference, and result processing
    """

    def __init__(self, model_type: DetectionModelType = DetectionModelType.FASTER_RCNN,
                 confidence_threshold: float = 0.5):
        self.model_type = model_type
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.transforms = None

        # Initialize the detection model
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the object detection model"""
        try:
            if self.model_type == DetectionModelType.FASTER_RCNN and TORCHVISION_AVAILABLE:
                self.model = fasterrcnn_resnet50_fpn(pretrained=True)
                self.model.eval()
                self.logger.info("Faster R-CNN model loaded successfully")
            elif self.model_type == DetectionModelType.SSD and TORCHVISION_AVAILABLE:
                self.model = ssd300_vgg16(pretrained=True)
                self.model.eval()
                self.logger.info("SSD model loaded successfully")
            elif self.model_type == DetectionModelType.MASK_RCNN and TORCHVISION_AVAILABLE:
                self.model = maskrcnn_resnet50_fpn(pretrained=True)
                self.model.eval()
                self.logger.info("Mask R-CNN model loaded successfully")
            else:
                self.logger.warning(f"Model type {self.model_type} not supported, using basic OpenCV detection")
                if not OPENCV_AVAILABLE:
                    self.logger.error("OpenCV not available for basic detection")
        except Exception as e:
            self.logger.error(f"Error initializing detection model: {e}")
            self.model = None

    async def detect_objects(self, image: np.ndarray,
                           return_masks: bool = False) -> List[DetectionResult]:
        """
        Detect objects in the input image

        Args:
            image: Input image as numpy array (H, W, C)
            return_masks: Whether to return segmentation masks (for Mask R-CNN)

        Returns:
            List of detection results
        """
        try:
            if self.model is not None and TORCH_AVAILABLE and TORCHVISION_AVAILABLE:
                return await self._detect_with_torchvision(image, return_masks)
            else:
                # Fallback to basic OpenCV detection
                return await self._detect_with_opencv(image)

        except Exception as e:
            self.logger.error(f"Error in object detection: {e}")
            return []

    async def _detect_with_torchvision(self, image: np.ndarray,
                                     return_masks: bool = False) -> List[DetectionResult]:
        """Perform object detection using TorchVision models"""
        if not TORCH_AVAILABLE or not TORCHVISION_AVAILABLE:
            self.logger.error("TorchVision not available for detection")
            return []

        try:
            # Convert numpy array to PIL Image and then to tensor
            if isinstance(image, np.ndarray):
                # Ensure image is in the right format (H, W, C) with values 0-255
                if image.dtype != np.uint8:
                    image = (image * 255).astype(np.uint8)

                # Convert to tensor (C, H, W) with values 0-1
                image_tensor = F.to_tensor(image)
            else:
                image_tensor = image

            # Add batch dimension
            image_batch = [image_tensor]

            # Perform inference
            with torch.no_grad():
                if return_masks and self.model_type == DetectionModelType.MASK_RCNN:
                    outputs = self.model(image_batch)
                    return self._process_maskrcnn_output(outputs[0], image.shape[:2])
                else:
                    outputs = self.model(image_batch)
                    return self._process_detection_output(outputs[0], image.shape[:2])

        except Exception as e:
            self.logger.error(f"Error in TorchVision detection: {e}")
            # Fallback to OpenCV
            return await self._detect_with_opencv(image)

    def _process_detection_output(self, output: Dict[str, torch.Tensor],
                                image_shape: Tuple[int, int]) -> List[DetectionResult]:
        """Process detection output from TorchVision models"""
        results = []

        # Get the relevant tensors
        boxes = output['boxes'].cpu().numpy()
        scores = output['scores'].cpu().numpy()
        labels = output['labels'].cpu().numpy()

        # COCO dataset class names (first 20 classes for example)
        coco_names = [
            '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
            'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
            'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag',
            'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
            'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana',
            'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
            'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'dining table',
            'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
            'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock',
            'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]

        for i in range(len(boxes)):
            if scores[i] >= self.confidence_threshold:
                box = boxes[i]
                x1, y1, x2, y2 = map(int, box)
                w, h = x2 - x1, y2 - y1

                # Convert to (x, y, width, height) format
                bbox = (x1, y1, w, h)
                center_x, center_y = x1 + w // 2, y1 + h // 2

                class_name = coco_names[labels[i]] if labels[i] < len(coco_names) else f"object_{labels[i]}"

                result = DetectionResult(
                    object_id=f"obj_{i}_{class_name}",
                    class_name=class_name,
                    confidence=float(scores[i]),
                    bounding_box=bbox,
                    position_2d=(center_x, center_y)
                )

                results.append(result)

        return results

    def _process_maskrcnn_output(self, output: Dict[str, torch.Tensor],
                               image_shape: Tuple[int, int]) -> List[DetectionResult]:
        """Process output from Mask R-CNN model"""
        results = self._process_detection_output(output, image_shape)

        # Add masks if available
        if 'masks' in output:
            masks = output['masks'].cpu().numpy()
            for i, result in enumerate(results):
                if i < len(masks):
                    # Extract the mask for this detection
                    mask = masks[i, 0]  # Shape is [N, 1, H, W]
                    result.segmentation_mask = mask

        return results

    async def _detect_with_opencv(self, image: np.ndarray) -> List[DetectionResult]:
        """Perform basic object detection using OpenCV (fallback method)"""
        if not OPENCV_AVAILABLE:
            self.logger.error("OpenCV not available for basic detection")
            return []

        try:
            # Convert image to grayscale for basic processing
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.shape[2] == 3 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Use adaptive thresholding to identify regions of interest
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

            # Find contours which represent potential objects
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            results = []
            object_id = 0

            for contour in contours:
                # Filter out very small contours
                area = cv2.contourArea(contour)
                if area > 100:  # Minimum area threshold
                    # Get bounding box
                    x, y, w, h = cv2.boundingRect(contour)

                    # Calculate center
                    center_x, center_y = x + w // 2, y + h // 2

                    # Estimate confidence based on size (larger objects more likely to be real)
                    confidence = min(0.9, area / 10000)  # Normalize by a large area

                    result = DetectionResult(
                        object_id=f"obj_{object_id}",
                        class_name="object",  # Unknown class in basic detection
                        confidence=confidence,
                        bounding_box=(x, y, w, h),
                        position_2d=(center_x, center_y)
                    )

                    results.append(result)
                    object_id += 1

            # Sort results by confidence (descending)
            results.sort(key=lambda x: x.confidence, reverse=True)

            return results

        except Exception as e:
            self.logger.error(f"Error in OpenCV detection: {e}")
            return []

    async def detect_specific_objects(self, image: np.ndarray,
                                    target_classes: List[str]) -> List[DetectionResult]:
        """
        Detect only specific object classes

        Args:
            image: Input image
            target_classes: List of class names to detect

        Returns:
            List of detection results for specified classes
        """
        all_detections = await self.detect_objects(image)
        filtered_detections = [
            detection for detection in all_detections
            if detection.class_name.lower() in [cls.lower() for cls in target_classes]
        ]
        return filtered_detections

    async def track_objects(self, current_image: np.ndarray,
                          previous_detections: List[DetectionResult],
                          use_optical_flow: bool = True) -> List[DetectionResult]:
        """
        Track objects across frames using detection and optional optical flow

        Args:
            current_image: Current frame
            previous_detections: Detections from previous frame
            use_optical_flow: Whether to use optical flow for tracking

        Returns:
            Updated detection results with tracking IDs
        """
        # For now, just perform fresh detection
        # In a real implementation, you would implement tracking logic
        current_detections = await self.detect_objects(current_image)

        # Simple association based on position proximity
        if previous_detections:
            current_detections = self._associate_detections(previous_detections, current_detections)

        return current_detections

    def _associate_detections(self, previous: List[DetectionResult],
                            current: List[DetectionResult],
                            max_distance: int = 50) -> List[DetectionResult]:
        """Associate current detections with previous ones based on position"""
        updated_current = []

        for curr_det in current:
            best_match = None
            best_distance = float('inf')

            for prev_det in previous:
                # Calculate distance between centers
                curr_center = curr_det.position_2d
                prev_center = prev_det.position_2d

                distance = np.sqrt((curr_center[0] - prev_center[0])**2 +
                                 (curr_center[1] - prev_center[1])**2)

                if distance < max_distance and distance < best_distance:
                    best_distance = distance
                    best_match = prev_det

            # If we found a good match, keep the previous ID
            if best_match is not None:
                updated_det = DetectionResult(
                    object_id=best_match.object_id,  # Keep previous ID
                    class_name=curr_det.class_name,
                    confidence=curr_det.confidence,
                    bounding_box=curr_det.bounding_box,
                    position_2d=curr_det.position_2d,
                    segmentation_mask=curr_det.segmentation_mask,
                    features=curr_det.features
                )
                updated_current.append(updated_det)
            else:
                # New object detected
                updated_current.append(curr_det)

        return updated_current

    async def get_object_features(self, image: np.ndarray,
                                detection: DetectionResult) -> Optional[np.ndarray]:
        """
        Extract features from a detected object for similarity matching

        Args:
            image: Original image
            detection: Detection result to extract features from

        Returns:
            Feature vector or None if not available
        """
        try:
            # Extract the region of interest
            x, y, w, h = detection.bounding_box
            roi = image[y:y+h, x:x+w]

            if TORCH_AVAILABLE:
                # Convert to tensor and normalize
                roi_tensor = F.to_tensor(roi).unsqueeze(0)  # Add batch dimension

                # In a real implementation, you would pass this through a feature extractor
                # For now, return a simple representation
                features = np.mean(roi.astype(np.float32), axis=(0, 1))  # Average color
                return features.astype(np.float32)
            else:
                # Fallback: simple color histogram
                if OPENCV_AVAILABLE:
                    hist_features = []
                    for i in range(roi.shape[2] if len(roi.shape) > 2 else 1):
                        channel = roi[:, :, i] if len(roi.shape) > 2 else roi
                        hist = cv2.calcHist([channel], [0], None, [8], [0, 256])
                        hist_features.extend(hist.flatten())
                    return np.array(hist_features, dtype=np.float32)

        except Exception as e:
            self.logger.error(f"Error extracting features: {e}")
            return None


class ObjectDetectionPipeline:
    """
    Complete pipeline for object detection in VLA system
    Integrates with other VLA components
    """

    def __init__(self, detection_manager: ObjectDetectionManager):
        self.detection_manager = detection_manager
        self.logger = logging.getLogger(__name__)

    async def process_frame(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Complete processing of a single image frame

        Returns:
            Dictionary with detection results and metadata
        """
        try:
            # Perform object detection
            detections = await self.detection_manager.detect_objects(image)

            # Prepare results
            results = {
                'detections': detections,
                'count': len(detections),
                'timestamp': asyncio.get_event_loop().time(),
                'image_shape': image.shape
            }

            # Add additional processing if needed
            for detection in detections:
                # Extract features for each detection
                features = await self.detection_manager.get_object_features(image, detection)
                detection.features = features

            return results

        except Exception as e:
            self.logger.error(f"Error in frame processing: {e}")
            return {
                'detections': [],
                'count': 0,
                'timestamp': asyncio.get_event_loop().time(),
                'error': str(e)
            }

    async def process_video_stream(self, frame_generator,
                                 max_frames: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Process a video stream frame by frame

        Args:
            frame_generator: Generator that yields image frames
            max_frames: Maximum number of frames to process (None for all)

        Returns:
            List of processing results for each frame
        """
        results = []
        frame_count = 0

        async for frame in frame_generator:
            result = await self.process_frame(frame)
            results.append(result)
            frame_count += 1

            if max_frames and frame_count >= max_frames:
                break

        return results


# Example usage and testing
async def test_object_detection():
    """Test the object detection functionality"""
    print("Testing Object Detection Integration")
    print("=" * 40)

    # Create detection manager
    detector = ObjectDetectionManager(confidence_threshold=0.3)

    # Create a dummy image for testing
    if OPENCV_AVAILABLE:
        import numpy as np
        dummy_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    else:
        dummy_image = np.random.random((100, 100, 3)).astype(np.uint8)

    print("\n1. Testing general object detection...")
    detections = await detector.detect_objects(dummy_image)
    print(f"   Detected {len(detections)} objects")
    for i, detection in enumerate(detections[:5]):  # Show top 5
        print(f"   {i+1}. {detection.class_name}: confidence {detection.confidence:.2f}, "
              f"position {detection.position_2d}")

    print("\n2. Testing specific object detection...")
    specific_detections = await detector.detect_specific_objects(
        dummy_image,
        ["person", "car", "cup", "bottle"]
    )
    print(f"   Found {len(specific_detections)} specific objects")
    for i, detection in enumerate(specific_detections):
        print(f"   {i+1}. {detection.class_name} with confidence {detection.confidence:.2f}")

    # Test with a more complex image if OpenCV is available
    if OPENCV_AVAILABLE:
        print("\n3. Testing with a more structured image...")
        # Create an image with some simple shapes
        test_image = np.zeros((200, 200, 3), dtype=np.uint8)
        # Add some shapes
        cv2.rectangle(test_image, (50, 50), (100, 100), (255, 0, 0), -1)  # Blue square
        cv2.circle(test_image, (150, 150), 25, (0, 255, 0), -1)  # Green circle

        shape_detections = await detector.detect_objects(test_image)
        print(f"   Detected {len(shape_detections)} shapes in test image")

    print("\nObject detection integration test completed!")


if __name__ == "__main__":
    asyncio.run(test_object_detection())