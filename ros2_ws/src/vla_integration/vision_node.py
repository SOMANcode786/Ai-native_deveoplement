#!/usr/bin/env python3
"""
ROS 2 Vision Node for Object Recognition in Vision-Language-Action (VLA) System

This node integrates computer vision capabilities with ROS 2,
providing object detection and recognition for the VLA system.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy

# Import ROS 2 message types
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from geometry_msgs.msg import Point
from vla_interfaces.msg import ObjectDetection  # Custom message
from vla_interfaces.srv import VLAPrompt  # Custom service for vision queries

import cv2
import numpy as np
from cv_bridge import CvBridge
from typing import Optional, Dict, Any
import asyncio
import threading
import logging

# Import our vision modules
from src.vision_language.object_detection import ObjectDetectionManager, DetectionResult, DetectionModelType
from src.vision_language.grounding import VisionLanguageGrounding
from src.error_handling import ErrorHandler, VLALogger, VLAException, VLAErrorType


class VisionNode(Node):
    """
    ROS 2 Node for computer vision and object recognition
    Subscribes to camera images, performs object detection, and publishes results
    """

    def __init__(self):
        super().__init__('vision_node')

        # Initialize logging
        self.logger = VLALogger('VisionNode')
        self.error_handler = ErrorHandler(self.logger)

        # Node parameters
        self.declare_parameter('detection_model', 'faster_rcnn')
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('enable_grounding', True)
        self.declare_parameter('camera_topic', '/camera/image_raw')
        self.declare_parameter('camera_info_topic', '/camera/camera_info')

        # Get parameters
        model_name = self.get_parameter('detection_model').get_parameter_value().string_value
        confidence_threshold = self.get_parameter('confidence_threshold').get_parameter_value().double_value
        enable_grounding = self.get_parameter('enable_grounding').get_parameter_value().bool_value

        # Initialize vision components
        try:
            # Convert model name to enum
            model_type = DetectionModelType(model_name)
            self.detection_manager = ObjectDetectionManager(
                model_type=model_type,
                confidence_threshold=confidence_threshold
            )

            self.grounding_enabled = enable_grounding
            if self.grounding_enabled:
                self.grounding_system = VisionLanguageGrounding()

            self.cv_bridge = CvBridge()
            self.latest_image = None
            self.latest_camera_info = None

            self.logger.info("Vision components initialized", component="VisionNode")
        except Exception as e:
            self.error_handler.handle_exception(e, "VisionNode.__init__")
            raise

        # Create publishers
        self.detection_pub = self.create_publisher(
            ObjectDetection,
            'vla/object_detections',
            QoSProfile(depth=10)
        )

        self.visualization_pub = self.create_publisher(
            Image,
            'vla/visualization',
            QoSProfile(depth=10)
        )

        self.status_pub = self.create_publisher(
            String,
            'vla/vision_status',
            QoSProfile(depth=10)
        )

        # Create subscribers
        camera_topic = self.get_parameter('camera_topic').get_parameter_value().string_value
        self.image_sub = self.create_subscription(
            Image,
            camera_topic,
            self.image_callback,
            QoSProfile(depth=5)
        )

        camera_info_topic = self.get_parameter('camera_info_topic').get_parameter_value().string_value
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            camera_info_topic,
            self.camera_info_callback,
            QoSProfile(depth=5)
        )

        # Create services
        self.grounding_srv = self.create_service(
            VLAPrompt,  # Using our custom service for vision queries
            'vla/ground_language_reference',
            self.ground_language_callback
        )

        # Create timers
        self.status_timer = self.create_timer(1.0, self.publish_status)

        self.logger.info("Vision node initialized", component="VisionNode")

    def image_callback(self, msg: Image):
        """
        Callback for camera image messages
        Performs object detection and publishes results
        """
        try:
            self.logger.info(f"Received image: {msg.width}x{msg.height}", component="VisionNode")

            # Convert ROS Image to OpenCV image
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.latest_image = cv_image

            # Perform object detection
            future = asyncio.run_coroutine_threadsafe(
                self.process_image_async(cv_image),
                self.get_async_loop()
            )

        except Exception as e:
            self.error_handler.handle_exception(e, "VisionNode.image_callback")

    def camera_info_callback(self, msg: CameraInfo):
        """
        Callback for camera info messages
        Stores camera intrinsics for 3D position calculation
        """
        try:
            self.logger.info("Received camera info", component="VisionNode")
            self.latest_camera_info = msg

        except Exception as e:
            self.error_handler.handle_exception(e, "VisionNode.camera_info_callback")

    async def process_image_async(self, cv_image: np.ndarray):
        """
        Process image asynchronously for object detection
        """
        try:
            self.logger.info("Starting object detection", component="VisionNode")

            # Perform object detection
            detections = await self.detection_manager.detect_objects(cv_image)

            if detections:
                self.logger.info(f"Detected {len(detections)} objects", component="VisionNode")

                # Publish detection results
                for detection in detections:
                    detection_msg = self._create_detection_message(detection, cv_image.shape)
                    self.detection_pub.publish(detection_msg)

                # Create visualization
                vis_image = self._draw_detections(cv_image, detections)
                vis_msg = self.cv_bridge.cv2_to_imgmsg(vis_image, encoding='bgr8')
                self.visualization_pub.publish(vis_msg)

            else:
                self.logger.info("No objects detected", component="VisionNode")

        except Exception as e:
            self.error_handler.handle_exception(e, "VisionNode.process_image_async")

    def _create_detection_message(self, detection: DetectionResult, image_shape: tuple) -> ObjectDetection:
        """Create ROS message from detection result"""
        detection_msg = ObjectDetection()
        detection_msg.header.stamp = self.get_clock().now().to_msg()
        detection_msg.header.frame_id = 'camera_frame'  # This should come from camera info

        detection_msg.object_id = detection.object_id
        detection_msg.class_name = detection.class_name
        detection_msg.confidence = detection.confidence

        # Convert bounding box coordinates
        x, y, w, h = detection.bounding_box
        detection_msg.bounding_box.x_offset = x
        detection_msg.bounding_box.y_offset = y
        detection_msg.bounding_box.width = w
        detection_msg.bounding_box.height = h

        # Convert 2D position
        center_x, center_y = detection.position_2d
        detection_msg.position_2d.x = float(center_x)
        detection_msg.position_2d.y = float(center_y)
        detection_msg.position_2d.z = 0.0  # 2D position

        # If we have 3D position (would need camera info and depth)
        # For now, we'll just use the 2D position
        detection_msg.position_3d.x = float(center_x)
        detection_msg.position_3d.y = float(center_y)
        detection_msg.position_3d.z = 1.0  # Placeholder depth

        return detection_msg

    def _draw_detections(self, image: np.ndarray, detections: list) -> np.ndarray:
        """Draw detection results on image for visualization"""
        vis_image = image.copy()

        for detection in detections:
            x, y, w, h = detection.bounding_box

            # Draw bounding box
            color = (0, 255, 0)  # Green
            thickness = 2
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, thickness)

            # Draw label
            label = f"{detection.class_name}: {detection.confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            label_y = max(y, label_size[1])

            cv2.putText(
                vis_image,
                label,
                (x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )

        return vis_image

    def ground_language_callback(self, request: VLAPrompt.Request, response: VLAPrompt.Response):
        """
        Service callback for grounding language references to objects
        """
        try:
            self.logger.info(f"Grounding request: {request.natural_language_command}", component="VisionNode")

            if not self.grounding_enabled:
                response.success = False
                response.message = "Grounding not enabled"
                response.action_sequence = []
                return response

            if self.latest_image is None:
                response.success = False
                response.message = "No image available for grounding"
                response.action_sequence = []
                return response

            # Perform grounding
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                grounding_results = loop.run_until_complete(
                    self.ground_language_async(
                        self.latest_image,
                        request.natural_language_command
                    )
                )
            finally:
                loop.close()

            if grounding_results:
                # Prepare response
                response.success = True
                response.message = f"Grounded to {len(grounding_results)} objects"
                # Convert grounding results to action sequence format
                response.action_sequence = [
                    f"Grounded '{result.language_query}' to {result.object_class} (ID: {result.object_id})"
                    for result in grounding_results[:3]  # Limit to top 3 results
                ]
            else:
                response.success = False
                response.message = "No objects found matching the description"
                response.action_sequence = []

        except Exception as e:
            self.error_handler.handle_exception(e, "VisionNode.ground_language_callback")
            response.success = False
            response.message = f"Error in grounding: {str(e)}"
            response.action_sequence = []

        return response

    async def ground_language_async(self, image: np.ndarray, language_query: str) -> list:
        """
        Ground language query to objects in the image asynchronously
        """
        try:
            results = await self.grounding_system.ground_language_reference(
                image,
                language_query
            )

            self.logger.info(f"Grounded '{language_query}' to {len(results)} objects", component="VisionNode")
            return results

        except Exception as e:
            self.error_handler.handle_exception(e, "VisionNode.ground_language_async")
            return []

    def publish_status(self):
        """Publish node status"""
        status_msg = String()
        status_msg.data = f"Vision node active - Detections: {0 if not hasattr(self, 'detection_manager') else 1}"
        self.status_pub.publish(status_msg)

    def get_async_loop(self):
        """
        Get or create an asyncio event loop for this node
        """
        if not hasattr(self, '_async_loop'):
            self._async_loop = asyncio.new_event_loop()
            # Start the event loop in a separate thread
            self._loop_thread = threading.Thread(target=self._async_loop.run_forever, daemon=True)
            self._loop_thread.start()

        return self._async_loop


class VisionClient:
    """
    Client class for interacting with the Vision Node
    Provides convenient methods for vision-related services
    """

    def __init__(self, node: Node):
        self.node = node
        self.logger = VLALogger('VisionClient')

        # Create client for grounding service
        self.grounding_client = self.node.create_client(VLAPrompt, 'vla/ground_language_reference')

        # Wait for service to be available
        while not self.grounding_client.wait_for_service(timeout_sec=1.0):
            self.logger.info('Vision grounding service not available, waiting again...', component="VisionClient")

    async def ground_language_reference(self, language_query: str) -> Optional[list]:
        """
        Request grounding of a language reference to objects in the current scene
        """
        try:
            # Create request
            request = VLAPrompt.Request()
            request.natural_language_command = language_query
            request.context = ""  # No additional context for vision grounding

            # Call service
            future = self.grounding_client.call_async(request)
            await future

            response = future.result()

            if response.success:
                self.logger.info(f"Grounded query: {language_query[:30]}...", component="VisionClient")
                return response.action_sequence
            else:
                self.logger.error(f"Grounding failed: {response.message}", component="VisionClient")
                return None

        except Exception as e:
            self.logger.error(f"Error calling grounding service: {e}", component="VisionClient")
            return None


def main(args=None):
    """Main function to run the vision node"""
    rclpy.init(args=args)

    try:
        node = VisionNode()
        node.logger.info("Starting Vision Node", component="VisionNode")

        # Spin the node
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.logger.info("Interrupted by user", component="VisionNode")
    except Exception as e:
        if 'node' in locals():
            node.error_handler.handle_exception(e, "VisionNode.main")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


# Additional utilities for vision in ROS 2 context
class ROS2VisionUtils:
    """Utilities for vision processing in ROS 2 context"""

    @staticmethod
    def image_msg_to_numpy(image_msg: Image) -> np.ndarray:
        """
        Convert ROS Image message to numpy array
        """
        try:
            bridge = CvBridge()
            cv_image = bridge.imgmsg_to_cv2(image_msg, desired_encoding='bgr8')
            return cv_image
        except Exception as e:
            raise RuntimeError(f"Failed to convert image message to numpy: {e}")

    @staticmethod
    def numpy_to_image_msg(np_image: np.ndarray, encoding: str = 'bgr8') -> Image:
        """
        Convert numpy array to ROS Image message
        """
        try:
            bridge = CvBridge()
            image_msg = bridge.cv2_to_imgmsg(np_image, encoding=encoding)
            return image_msg
        except Exception as e:
            raise RuntimeError(f"Failed to convert numpy to image message: {e}")

    @staticmethod
    def calculate_3d_position(pixel_x: int, pixel_y: int, depth: float,
                            camera_info: CameraInfo) -> Point:
        """
        Calculate 3D position from 2D pixel coordinates and depth
        """
        # This is a simplified calculation - in practice, you'd use the full camera matrix
        point = Point()

        # Get camera parameters
        center_x = camera_info.k[2]  # cx
        center_y = camera_info.k[5]  # cy
        focal_x = camera_info.k[0]  # fx
        focal_y = camera_info.k[4]  # fy

        # Calculate 3D position
        point.x = (pixel_x - center_x) * depth / focal_x
        point.y = (pixel_y - center_y) * depth / focal_y
        point.z = depth

        return point


# Example usage and testing
async def vision_node_demo():
    """
    Demonstrate the vision node capabilities
    """
    print("Vision Node Demo")
    print("=" * 40)

    # This would normally run within a ROS 2 context
    # For demonstration, we'll show the conceptual usage:

    print("\n1. Vision node provides object detection services:")
    print("   - Subscribes to camera topics")
    print("   - Performs real-time object detection")
    print("   - Publishes detection results")

    print("\n2. Vision-language grounding capabilities:")
    print("   - Links language descriptions to visual objects")
    print("   - Supports spatial relationships")
    print("   - Provides confidence scores")

    print("\n3. Integration with VLA system:")
    print("   - ROS 2 message passing")
    print("   - Service-based architecture")
    print("   - Real-time processing")

    print("\nVision node ready for VLA system integration!")


if __name__ == '__main__':
    # For now, just run the example
    # In a real ROS 2 environment, this would start the vision node
    asyncio.run(vision_node_demo())