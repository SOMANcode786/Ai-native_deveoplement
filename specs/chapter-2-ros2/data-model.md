# Data Model: Chapter 2 - The Robotic Nervous System (ROS 2)

## Overview
This document defines the data structures and message types that will be covered in Chapter 2. These represent the core ROS 2 message types that readers will encounter when working with ROS 2 systems.

## Standard Message Types (std_msgs)

### String
- **Package**: `std_msgs`
- **Definition**: Simple string message
- **Fields**:
  - `data: string` - The string data
- **Usage**: General text communication, status messages
- **Example**:
  ```python
  from std_msgs.msg import String
  msg = String()
  msg.data = "Hello, ROS 2!"
  ```

### Basic Data Types
- **Int8, Int16, Int32, Int64**: Signed integer types
- **UInt8, UInt16, UInt32, UInt64**: Unsigned integer types
- **Float32, Float64**: Floating point types
- **Bool**: Boolean type (True/False)
- **Byte**: Single byte (UInt8 alias)

## Sensor Message Types (sensor_msgs)

### LaserScan
- **Package**: `sensor_msgs`
- **Definition**: Laser range-finder data
- **Fields**:
  - `header: std_msgs/Header` - Timestamp and frame ID
  - `angle_min: float32` - Start angle of the scan [rad]
  - `angle_max: float32` - End angle of the scan [rad]
  - `angle_increment: float32` - Angular distance between measurements [rad]
  - `time_increment: float32` - Time between measurements [seconds]
  - `scan_time: float32` - Time between scans [seconds]
  - `range_min: float32` - Minimum range value [m]
  - `range_max: float32` - Maximum range value [m]
  - `ranges: float32[]` - Range data [m]
  - `intensities: float32[]` - Intensity data [device dependent]
- **Usage**: LIDAR sensor data, obstacle detection

### Image
- **Package**: `sensor_msgs`
- **Definition**: An image from a camera
- **Fields**:
  - `header: std_msgs/Header` - Timestamp and frame ID
  - `height: uint32` - Image height in pixels
  - `width: uint32` - Image width in pixels
  - `encoding: string` - Pixel encoding (RGB8, BGR8, etc.)
  - `is_bigendian: uint8` - 0 for little endian, 1 for big endian
  - `step: uint32` - Full row length in bytes
  - `data: uint8[]` - Image data as bytes
- **Usage**: Camera data, computer vision applications

### JointState
- **Package**: `sensor_msgs`
- **Definition**: State of a joint set
- **Fields**:
  - `header: std_msgs/Header` - Timestamp and frame ID
  - `name: string[]` - Joint names
  - `position: float64[]` - Joint positions [rad or m]
  - `velocity: float64[]` - Joint velocities [rad/s or m/s]
  - `effort: float64[]` - Joint efforts [Nm or N]
- **Usage**: Robot arm state, mobile base odometry

## Geometric Message Types (geometry_msgs)

### Point
- **Package**: `geometry_msgs`
- **Definition**: A point in 3D space
- **Fields**:
  - `x: float64` - X coordinate
  - `y: float64` - Y coordinate
  - `z: float64` - Z coordinate
- **Usage**: Position in 3D space

### Pose
- **Package**: `geometry_msgs`
- **Definition**: Position and orientation in 3D space
- **Fields**:
  - `position: geometry_msgs/Point` - Position in 3D space
  - `orientation: geometry_msgs/Quaternion` - Orientation as quaternion
- **Usage**: Robot pose, target position

### Twist
- **Package**: `geometry_msgs`
- **Definition**: Linear and angular velocities
- **Fields**:
  - `linear: geometry_msgs/Vector3` - Linear velocity
  - `angular: geometry_msgs/Vector3` - Angular velocity
- **Usage**: Robot motion commands, velocity feedback

### Quaternion
- **Package**: `geometry_msgs`
- **Definition**: Orientation in quaternion format
- **Fields**:
  - `x: float64` - X component
  - `y: float64` - Y component
  - `z: float64` - Z component
  - `w: float64` - W component
- **Usage**: 3D orientation representation

## Service Message Types

### SetBool
- **Package**: `std_srvs`
- **Request**:
  - `data: bool` - Desired state
- **Response**:
  - `success: bool` - True if successful
  - `message: string` - Response message
- **Usage**: Simple on/off services

### Trigger
- **Package**: `std_srvs`
- **Request**: Empty
- **Response**:
  - `success: bool` - True if successful
  - `message: string` - Response message
- **Usage**: Simple trigger services

## Action Message Types

### Fibonacci
- **Package**: `action_tutorials_interfaces` (example)
- **Goal**:
  - `order: int32` - Order of the Fibonacci sequence
- **Result**:
  - `sequence: int32[]` - Generated Fibonacci sequence
- **Feedback**:
  - `sequence: int32[]` - Current state of the sequence
- **Usage**: Example action demonstrating goal-based operations

## Message Design Patterns

### Header Pattern
- Most sensor and geometric messages include a `header` field
- Contains timestamp and frame_id for coordinate transformation
- Enables proper synchronization and spatial relationships

### Array Pattern
- Many messages use arrays for multiple values (e.g., ranges in LaserScan)
- Allows for variable-length data transmission
- Efficient for sensor data with multiple readings

### Nested Message Pattern
- Messages often contain other message types as fields
- Enables complex data structures while maintaining modularity
- Examples: Pose contains Point and Quaternion

## Quality of Service (QoS) Considerations

### Reliability
- `RMW_QOS_POLICY_RELIABILITY_RELIABLE`: All messages delivered
- `RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT`: Best effort delivery

### Durability
- `RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL`: Transient data for late joiners
- `RMW_QOS_POLICY_DURABILITY_VOLATILE`: Volatile data, no persistence

### History
- `RMW_QOS_POLICY_HISTORY_KEEP_LAST`: Keep last N messages
- `RMW_QOS_POLICY_HISTORY_KEEP_ALL`: Keep all messages

## Common Message Usage Scenarios

### Navigation
- `geometry_msgs/Twist` for velocity commands
- `sensor_msgs/LaserScan` for obstacle detection
- `nav_msgs/Odometry` for position tracking

### Manipulation
- `sensor_msgs/JointState` for arm positioning
- `geometry_msgs/Pose` for end-effector position
- `control_msgs/JointTrajectory` for trajectory control

### Perception
- `sensor_msgs/Image` for camera data
- `sensor_msgs/PointCloud2` for 3D point clouds
- `geometry_msgs/Point` for detected object positions