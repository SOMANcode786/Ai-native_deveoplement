"""
Error Handling and Logging Infrastructure for Vision-Language-Action (VLA) System

This module provides centralized error handling, logging, and exception management
for all VLA components.
"""

import logging
import sys
import traceback
from typing import Optional, Dict, Any, Callable
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
import json


class VLAErrorType(Enum):
    """Types of errors in the VLA system"""
    LLM_ERROR = "llm_error"
    SPEECH_RECOGNITION_ERROR = "speech_recognition_error"
    ROS_ERROR = "ros_error"
    VISION_ERROR = "vision_error"
    CONFIGURATION_ERROR = "configuration_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class VLAError:
    """Represents an error in the VLA system"""
    error_type: VLAErrorType
    message: str
    component: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    traceback_str: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "traceback": self.traceback_str
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class VLAException(Exception):
    """Base exception class for VLA system"""
    def __init__(self, error_type: VLAErrorType, message: str, component: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.component = component
        self.details = details or {}
        self.timestamp = datetime.now()
        self.vla_error = VLAError(
            error_type=error_type,
            message=message,
            component=component,
            timestamp=self.timestamp,
            details=details,
            traceback_str=traceback.format_stack()
        )

    def to_vla_error(self) -> VLAError:
        """Convert to VLAError object"""
        return self.vla_error


class VLALogger:
    """Custom logger for VLA system with specialized error handling"""

    def __init__(self, name: str = "VLA", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Prevent adding handlers multiple times
        if not self.logger.handlers:
            # Create console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)

            # Create file handler
            file_handler = logging.FileHandler("vla_system.log")
            file_handler.setLevel(level)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)

            # Add handlers to logger
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

    def debug(self, message: str, component: str = "unknown"):
        """Log debug message"""
        self.logger.debug(f"[{component}] {message}")

    def info(self, message: str, component: str = "unknown"):
        """Log info message"""
        self.logger.info(f"[{component}] {message}")

    def warning(self, message: str, component: str = "unknown"):
        """Log warning message"""
        self.logger.warning(f"[{component}] {message}")

    def error(self, message: str, component: str = "unknown", exception: Optional[Exception] = None):
        """Log error message with optional exception"""
        if exception:
            self.logger.error(f"[{component}] {message}", exc_info=True)
        else:
            self.logger.error(f"[{component}] {message}")

    def critical(self, message: str, component: str = "unknown"):
        """Log critical message"""
        self.logger.critical(f"[{component}] {message}")


class ErrorHandler:
    """Centralized error handler for VLA system"""

    def __init__(self, logger: Optional[VLALogger] = None):
        self.logger = logger or VLALogger()
        self.error_handlers: Dict[VLAErrorType, Callable] = {}
        self.error_count = 0

    def register_error_handler(self, error_type: VLAErrorType, handler: Callable):
        """Register a custom error handler for a specific error type"""
        self.error_handlers[error_type] = handler

    def handle_error(self, error: VLAException, should_raise: bool = True) -> Optional[VLAError]:
        """Handle an error with appropriate logging and processing"""
        self.error_count += 1
        error_obj = error.to_vla_error()

        # Log the error
        self.logger.error(
            f"VLA Error [{error_obj.error_type.value}] in {error_obj.component}: {error_obj.message}",
            component=error_obj.component,
            exception=error
        )

        # Call specific error handler if registered
        if error_obj.error_type in self.error_handlers:
            try:
                self.error_handlers[error_obj.error_type](error_obj)
            except Exception as handler_error:
                self.logger.error(
                    f"Error in error handler for {error_obj.error_type}: {handler_error}",
                    component="ErrorHandler"
                )

        # Write error to error log file
        self._log_error_to_file(error_obj)

        if should_raise:
            raise error

        return error_obj

    def handle_exception(self, exc: Exception, component: str, error_type: Optional[VLAErrorType] = None) -> VLAError:
        """Handle a generic exception and convert to VLA error"""
        if isinstance(exc, VLAException):
            # If it's already a VLAException, handle it directly
            return self.handle_error(exc, should_raise=False)

        # Determine error type based on exception type
        if error_type is None:
            error_type = self._infer_error_type(exc)

        vla_error = VLAException(
            error_type=error_type,
            message=str(exc),
            component=component,
            details={"exception_type": type(exc).__name__}
        )

        return self.handle_error(vla_error, should_raise=False)

    def _infer_error_type(self, exc: Exception) -> VLAErrorType:
        """Infer error type from exception"""
        exc_name = type(exc).__name__.lower()

        if 'llm' in exc_name or 'openai' in exc_name or 'anthropic' in exc_name:
            return VLAErrorType.LLM_ERROR
        elif 'speech' in exc_name or 'audio' in exc_name or 'whisper' in exc_name:
            return VLAErrorType.SPEECH_RECOGNITION_ERROR
        elif 'ros' in exc_name or 'rclpy' in exc_name:
            return VLAErrorType.ROS_ERROR
        elif 'vision' in exc_name or 'cv2' in exc_name or 'image' in exc_name:
            return VLAErrorType.VISION_ERROR
        elif 'config' in exc_name or 'env' in exc_name:
            return VLAErrorType.CONFIGURATION_ERROR
        elif 'network' in exc_name or 'connection' in exc_name or 'timeout' in exc_name:
            return VLAErrorType.NETWORK_ERROR
        elif 'validation' in exc_name or 'value' in exc_name:
            return VLAErrorType.VALIDATION_ERROR
        elif 'execution' in exc_name or 'runtime' in exc_name:
            return VLAErrorType.EXECUTION_ERROR
        else:
            return VLAErrorType.UNKNOWN_ERROR

    def _log_error_to_file(self, error: VLAError):
        """Log error to a dedicated error log file"""
        try:
            with open("vla_errors.log", "a") as f:
                f.write(f"{error.to_json()}\n")
        except Exception as e:
            # If we can't log the error, at least print it
            print(f"Could not write error to log file: {e}")

    def get_error_count(self) -> int:
        """Get the total number of errors handled"""
        return self.error_count

    def reset_error_count(self):
        """Reset the error counter"""
        self.error_count = 0


class RetryHandler:
    """Handles retry logic for operations that may fail"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor

    async def execute_with_retry(self, operation: Callable, component: str,
                                error_handler: ErrorHandler) -> Any:
        """Execute an operation with retry logic"""
        import asyncio

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = self.base_delay * (self.backoff_factor ** attempt)
                    error_handler.logger.warning(
                        f"Attempt {attempt + 1} failed for {component}, retrying in {delay}s: {e}",
                        component=component
                    )
                    await asyncio.sleep(delay)
                else:
                    error_handler.logger.error(
                        f"All {self.max_retries + 1} attempts failed for {component}: {e}",
                        component=component
                    )

        # If we get here, all retries failed
        raise last_exception

    def execute_with_retry_sync(self, operation: Callable, component: str,
                               error_handler: ErrorHandler) -> Any:
        """Execute a synchronous operation with retry logic"""
        import time

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = self.base_delay * (self.backoff_factor ** attempt)
                    error_handler.logger.warning(
                        f"Attempt {attempt + 1} failed for {component}, retrying in {delay}s: {e}",
                        component=component
                    )
                    time.sleep(delay)
                else:
                    error_handler.logger.error(
                        f"All {self.max_retries + 1} attempts failed for {component}: {e}",
                        component=component
                    )

        # If we get here, all retries failed
        raise last_exception


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_vla_error(error_type: VLAErrorType, message: str, component: str,
                    details: Optional[Dict[str, Any]] = None, should_raise: bool = True) -> Optional[VLAError]:
    """Convenience function to handle a VLA error"""
    error = VLAException(error_type, message, component, details)
    return get_error_handler().handle_error(error, should_raise)


def handle_exception(exc: Exception, component: str, error_type: Optional[VLAErrorType] = None) -> VLAError:
    """Convenience function to handle a generic exception"""
    return get_error_handler().handle_exception(exc, component, error_type)


# Example usage and testing
if __name__ == "__main__":
    # Initialize error handler
    handler = get_error_handler()
    logger = VLALogger()

    # Test different types of errors
    try:
        # Simulate an LLM error
        raise VLAException(
            VLAErrorType.LLM_ERROR,
            "Failed to connect to LLM API",
            "LLMManager",
            {"api_endpoint": "https://api.openai.com", "status_code": 500}
        )
    except VLAException as e:
        handler.handle_error(e, should_raise=False)

    # Test with a regular exception
    try:
        raise ConnectionError("Network timeout")
    except Exception as e:
        handler.handle_exception(e, "NetworkModule")

    print(f"Total errors handled: {handler.get_error_count()}")