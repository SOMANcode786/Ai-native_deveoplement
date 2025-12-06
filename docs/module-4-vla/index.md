# Vision-Language-Action (VLA) Integration

This module teaches students how to integrate large language models (LLMs) with robotic systems to enable conversational, cognitive robotics. Students will learn to translate natural language commands into a sequence of actionable ROS 2 commands, completing complex tasks.

## Table of Contents
1. [VLA Fundamentals](./fundamentals.md)
2. [Architecture](./architecture.md)
3. [Voice-to-Action Pipeline](./voice-to-action.md)
4. [LLM Integration](./llm-integration.md)
5. [Multi-Modal Perception](./multi-modal.md)
6. [Human-Robot Interaction](./hri.md)
7. [Cognitive Robotics vs Traditional Robotics](./cognitive-robotics.md)
8. [Assessments](./assessments.md)

## Overview

The Vision-Language-Action (VLA) framework represents a paradigm shift in robotics, bridging high-level cognitive models (LLMs) with low-level motion controllers (ROS 2). This approach enables robots to understand and execute complex natural language commands by breaking them down into executable action sequences.

The VLA loop consists of:
- **Input**: Natural language commands and visual perception
- **LLM Plan**: High-level planning using language models
- **Robot Action**: Execution of planned actions through ROS 2
- **Visual Feedback**: Sensory feedback for closed-loop control