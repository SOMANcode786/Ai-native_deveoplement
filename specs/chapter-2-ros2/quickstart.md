# Quickstart Guide: Chapter 2 - The Robotic Nervous System (ROS 2)

## Overview
This quickstart guide provides the essential steps to get started with ROS 2 (Robot Operating System 2) for Chapter 2 of the Physical AI & Humanoid Robotics book. Follow these steps to set up your ROS 2 environment and run your first ROS 2 examples.

## Prerequisites
- Ubuntu 22.04 LTS (recommended) or compatible Linux distribution
- Python 3.10 or higher
- At least 4GB of RAM (8GB recommended)
- Administrative (sudo) access to install packages
- Internet connection for package downloads

## Installation Steps for ROS 2 Humble Hawksbill

### 1. Set up Locale
Ensure your locale is set to UTF-8:
```bash
locale  # Check for UTF-8
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
```

### 2. Set up Sources
Add the ROS 2 apt repository:
```bash
sudo apt update && sudo apt install curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
```

### 3. Install ROS 2
Update package lists and install ROS 2 Humble:
```bash
sudo apt update
sudo apt install ros-humble-desktop
```

### 4. Install Python Dependencies
Install additional Python packages needed for development:
```bash
sudo apt install python3-colcon-common-extensions python3-rosdep python3-vcstool
sudo rosdep init
rosdep update
```

### 5. Source ROS 2 Environment
Add ROS 2 to your environment:
```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

## Verify Installation

### 1. Test Basic Commands
Check if ROS 2 is properly installed:
```bash
ros2 --version
```
You should see output similar to: `ros2 humble`

### 2. Run a Simple Publisher/Subscriber Example
Open two terminal windows and source ROS 2 in both:
```bash
source /opt/ros/humble/setup.bash
```

In the first terminal, run:
```bash
ros2 run demo_nodes_cpp talker
```

In the second terminal, run:
```bash
ros2 run demo_nodes_py listener
```

You should see messages being published by the talker and received by the listener.

## Creating Your First ROS 2 Package

### 1. Create a Workspace
```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws
```

### 2. Create a Package
```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_python my_robot_tutorials --dependencies rclpy std_msgs
```

### 3. Navigate to Package Directory
```bash
cd ~/ros2_ws/src/my_robot_tutorials
```

### 4. Basic Package Structure
Your package should have this structure:
```
my_robot_tutorials/
├── my_robot_tutorials/
│   ├── __init__.py
│   └── my_node.py
├── test/
├── package.xml
├── setup.cfg
├── setup.py
└── README.md
```

## Simple ROS 2 Node Example

Create a simple publisher node (`my_robot_tutorials/my_robot_tutorials/simple_publisher.py`):

```python
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class SimplePublisher(Node):
    def __init__(self):
        super().__init__('simple_publisher')
        self.publisher_ = self.create_publisher(String, 'chatter', 10)
        timer_period = 0.5  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = f'Hello World: {self.i}'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.i += 1


def main(args=None):
    rclpy.init(args=args)
    simple_publisher = SimplePublisher()
    rclpy.spin(simple_publisher)
    simple_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

### 1. Make the Script Executable
```bash
chmod +x my_robot_tutorials/my_robot_tutorials/simple_publisher.py
```

### 2. Update setup.py
Edit the `setup.py` file to include your new script in the entry points:

```python
entry_points={
    'console_scripts': [
        'simple_publisher = my_robot_tutorials.simple_publisher:main',
    ],
},
```

### 3. Build the Package
```bash
cd ~/ros2_ws
colcon build --packages-select my_robot_tutorials
```

### 4. Source the Workspace
```bash
source install/setup.bash
```

### 5. Run Your Node
```bash
ros2 run my_robot_tutorials simple_publisher
```

## Essential ROS 2 Commands

### Working with Nodes
```bash
ros2 node list                    # List active nodes
ros2 node info <node_name>        # Get info about a specific node
```

### Working with Topics
```bash
ros2 topic list                   # List active topics
ros2 topic echo <topic_name>      # Listen to a topic
ros2 topic info <topic_name>      # Get info about a topic
```

### Working with Services
```bash
ros2 service list                 # List active services
ros2 service call <service_name> <service_type> <request_data>
```

## Jetson Edge Kit Specific Instructions

### 1. Verify Jetson Platform
```bash
cat /etc/nv_tegra_release
```

### 2. Install Jetson-Specific Packages
```bash
sudo apt install ros-humble-ros-base
sudo apt install ros-humble-joint-state-publisher-gui
```

### 3. Optimize for Jetson
```bash
# Set environment variables for Jetson optimization
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
echo "export ROS_LOCALHOST_ONLY=1" >> ~/.bashrc
```

## Troubleshooting Common Issues

### 1. Permission Issues
If you encounter permission errors with devices:
```bash
sudo usermod -a -G dialout $USER
# Log out and log back in for changes to take effect
```

### 2. Network Discovery Issues
For network-related discovery problems:
```bash
export ROS_DOMAIN_ID=0  # Set a specific domain ID
export ROS_LOCALHOST_ONLY=1  # Use localhost only (for single machine)
```

### 3. Package Not Found
If packages aren't found after installation:
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
```

## Next Steps
- Complete the exercises in Chapter 2
- Experiment with different message types
- Try creating subscriber nodes to receive messages
- Explore ROS 2 services and actions
- Set up your development environment for the next chapter on simulation