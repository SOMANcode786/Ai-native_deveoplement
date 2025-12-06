"""
Configuration Management for Vision-Language-Action (VLA) System

This module provides centralized configuration management for all VLA components,
including LLM integration, speech recognition, and ROS 2 interfaces.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class VLAConfig:
    """Main configuration class for the VLA system"""

    # LLM Configuration
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-3.5-turbo"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1000
    llm_timeout: int = 30

    # Speech Recognition Configuration
    speech_provider: str = "whisper"
    speech_api_key: str = ""
    speech_model: str = "base"
    speech_language: str = "en"
    speech_sample_rate: int = 16000

    # ROS 2 Configuration
    ros_domain_id: int = 0
    ros_namespace: str = "/vla"

    # General Configuration
    debug_mode: bool = False
    log_level: str = "INFO"
    data_directory: str = "./data"
    config_file_path: str = "./config.yaml"


class ConfigManager:
    """Manages loading, validating, and saving VLA configurations"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "./config.yaml"
        self.config = self._load_config()

    def _load_config(self) -> VLAConfig:
        """Load configuration from file, environment variables, or defaults"""
        config = VLAConfig()

        # Load from file if it exists
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                try:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        # Update config with values from file
                        for key, value in file_config.items():
                            if hasattr(config, key):
                                setattr(config, key, value)
                except yaml.YAMLError as e:
                    print(f"Warning: Could not parse config file {self.config_path}: {e}")

        # Override with environment variables
        config = self._load_from_env(config)

        return config

    def _load_from_env(self, config: VLAConfig) -> VLAConfig:
        """Load configuration values from environment variables"""
        # LLM Configuration
        config.llm_api_key = os.getenv('LLM_API_KEY', config.llm_api_key)
        config.llm_provider = os.getenv('LLM_PROVIDER', config.llm_provider)
        config.llm_model = os.getenv('LLM_MODEL', config.llm_model)

        # Speech Recognition Configuration
        config.speech_api_key = os.getenv('SPEECH_API_KEY', config.speech_api_key)
        config.speech_provider = os.getenv('SPEECH_PROVIDER', config.speech_provider)
        config.speech_model = os.getenv('SPEECH_MODEL', config.speech_model)

        # General Configuration
        config.debug_mode = os.getenv('DEBUG_MODE', str(config.debug_mode)).lower() == 'true'
        config.log_level = os.getenv('LOG_LEVEL', config.log_level)
        config.data_directory = os.getenv('DATA_DIRECTORY', config.data_directory)

        return config

    def save_config(self, config_path: Optional[str] = None) -> bool:
        """Save current configuration to file"""
        path = config_path or self.config_path
        try:
            config_dict = asdict(self.config)
            with open(path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving config to {path}: {e}")
            return False

    def get_config(self) -> VLAConfig:
        """Get the current configuration"""
        return self.config

    def update_config(self, **kwargs) -> bool:
        """Update configuration values"""
        try:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                else:
                    print(f"Warning: Unknown configuration key {key}")
            return True
        except Exception as e:
            print(f"Error updating config: {e}")
            return False

    def validate_config(self) -> bool:
        """Validate that the configuration is complete and valid"""
        errors = []

        # Validate LLM configuration
        if self.config.llm_provider in ['openai', 'anthropic'] and not self.config.llm_api_key:
            errors.append("LLM API key is required for OpenAI/Anthropic providers")

        # Validate speech recognition configuration
        if self.config.speech_provider in ['google', 'azure', 'aws'] and not self.config.speech_api_key:
            errors.append("Speech recognition API key is required for Google/Azure/AWS providers")

        # Validate model names
        valid_llm_providers = ['openai', 'anthropic', 'ollama', 'huggingface']
        if self.config.llm_provider not in valid_llm_providers:
            errors.append(f"Invalid LLM provider: {self.config.llm_provider}")

        valid_speech_providers = ['whisper', 'google', 'azure', 'aws']
        if self.config.speech_provider not in valid_speech_providers:
            errors.append(f"Invalid speech provider: {self.config.speech_provider}")

        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True


def create_default_config(config_path: str = "./config.yaml") -> bool:
    """Create a default configuration file"""
    default_config = VLAConfig()
    try:
        config_dict = asdict(default_config)
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
        print(f"Created default configuration at {config_path}")
        return True
    except Exception as e:
        print(f"Error creating default config: {e}")
        return False


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_vla_config() -> VLAConfig:
    """Get the current VLA configuration"""
    return get_config_manager().get_config()


def init_config(config_path: Optional[str] = None) -> bool:
    """Initialize the configuration manager"""
    global _config_manager
    try:
        _config_manager = ConfigManager(config_path)
        return _config_manager.validate_config()
    except Exception as e:
        print(f"Error initializing configuration: {e}")
        return False


# Example usage
if __name__ == "__main__":
    # Initialize configuration
    success = init_config()
    if success:
        print("Configuration initialized successfully")
        config = get_vla_config()
        print(f"LLM Provider: {config.llm_provider}")
        print(f"Speech Provider: {config.speech_provider}")
        print(f"Debug Mode: {config.debug_mode}")
    else:
        print("Failed to initialize configuration")
        # Create default config
        create_default_config()