"""
Performance Optimizer for Vision-Language-Action (VLA) System

This module provides performance optimization across all VLA components,
including caching, parallel processing, and resource management.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
import functools
import weakref
from concurrent.futures import ThreadPoolExecutor
import threading
import queue


class OptimizationLevel(Enum):
    """Levels of optimization"""
    LIGHT = "light"      # Minimal optimization
    MEDIUM = "medium"    # Balanced optimization
    AGGRESSIVE = "aggressive"  # Maximum optimization


class ResourceType(Enum):
    """Types of resources to optimize"""
    COMPUTATIONAL = "computational"
    MEMORY = "memory"
    NETWORK = "network"
    IO = "io"


@dataclass
class PerformanceMetric:
    """Performance measurement data"""
    component_name: str
    operation: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    timestamp: float
    optimization_applied: bool = False


class CacheManager:
    """
    Manages caching across VLA components
    Implements LRU cache with TTL and size limits
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, float]] = {}  # (value, expiration_time)
        self.access_order = []  # For LRU eviction
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if it exists and is not expired"""
        with self.lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if time.time() < expiry:
                    # Move to end for LRU
                    if key in self.access_order:
                        self.access_order.remove(key)
                    self.access_order.append(key)
                    return value
                else:
                    # Expired, remove it
                    del self.cache[key]
                    if key in self.access_order:
                        self.access_order.remove(key)
            return None

    def set(self, key: str, value: Any):
        """Set value in cache with TTL"""
        with self.lock:
            current_time = time.time()
            expiry = current_time + self.ttl_seconds

            # Add to cache
            self.cache[key] = (value, expiry)

            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            # Evict oldest if over size limit
            while len(self.cache) > self.max_size:
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]

    def invalidate(self, key: str):
        """Remove specific key from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            current_time = time.time()
            active_entries = 0
            expired_entries = 0

            for key, (_, expiry) in self.cache.items():
                if current_time < expiry:
                    active_entries += 1
                else:
                    expired_entries += 1

            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'active_entries': active_entries,
                'expired_entries': expired_entries,
                'access_order_length': len(self.access_order)
            }


class ResourceOptimizer:
    """
    Optimizes resource usage across VLA components
    Manages computational, memory, and network resources
    """

    def __init__(self, optimization_level: OptimizationLevel = OptimizationLevel.MEDIUM):
        self.optimization_level = optimization_level
        self.cache_manager = CacheManager()
        self.executor_pool = ThreadPoolExecutor(max_workers=4)
        self.resource_usage: Dict[str, Dict[str, float]] = {}
        self.performance_metrics: List[PerformanceMetric] = []
        self.logger = logging.getLogger(__name__)
        self.component_resources: Dict[str, Dict[ResourceType, float]] = {}

    def optimize_computational_resources(self, component_name: str, operation: Callable) -> Callable:
        """Optimize computational resources for an operation"""
        @functools.wraps(operation)
        async def optimized_operation(*args, **kwargs):
            start_time = time.time()

            # Apply optimization based on level
            if self.optimization_level == OptimizationLevel.AGGRESSIVE:
                # Use cached results if available
                cache_key = f"{component_name}:{operation.__name__}:{hash(str(args) + str(kwargs))}"
                cached_result = self.cache_manager.get(cache_key)
                if cached_result is not None:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return cached_result

            try:
                # Execute the operation
                result = await operation(*args, **kwargs)

                # Cache result if appropriate
                if self.optimization_level in [OptimizationLevel.MEDIUM, OptimizationLevel.AGGRESSIVE]:
                    cache_key = f"{component_name}:{operation.__name__}:{hash(str(args) + str(kwargs))}"
                    self.cache_manager.set(cache_key, result)

                return result

            finally:
                execution_time = time.time() - start_time
                self._record_metric(component_name, operation.__name__, execution_time)

        return optimized_operation

    def optimize_memory_usage(self, component_name: str, operation: Callable) -> Callable:
        """Optimize memory usage for an operation"""
        @functools.wraps(operation)
        async def optimized_operation(*args, **kwargs):
            # Monitor memory usage before operation
            memory_before = self._get_memory_usage()

            try:
                result = await operation(*args, **kwargs)

                # Monitor memory usage after operation
                memory_after = self._get_memory_usage()
                memory_used = memory_after - memory_before

                # Store resource usage
                if component_name not in self.component_resources:
                    self.component_resources[component_name] = {}
                self.component_resources[component_name][ResourceType.MEMORY] = memory_used

                return result

            except Exception as e:
                self.logger.error(f"Memory optimization error in {component_name}: {e}")
                raise

        return optimized_operation

    def optimize_network_usage(self, component_name: str, operation: Callable) -> Callable:
        """Optimize network usage for an operation"""
        @functools.wraps(operation)
        async def optimized_operation(*args, **kwargs):
            # For network operations, implement batching or compression
            # This is a simplified version - in practice, you'd have more sophisticated network optimizations
            try:
                result = await operation(*args, **kwargs)

                # Record network usage metrics
                if component_name not in self.component_resources:
                    self.component_resources[component_name] = {}
                self.component_resources[component_name][ResourceType.NETWORK] = self._estimate_network_usage(result)

                return result

            except Exception as e:
                self.logger.error(f"Network optimization error in {component_name}: {e}")
                raise

        return optimized_operation

    def _get_memory_usage(self) -> float:
        """Get current memory usage (simplified)"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            # Fallback if psutil is not available
            return 0.0

    def _estimate_network_usage(self, result: Any) -> float:
        """Estimate network usage for a result"""
        try:
            import sys
            return sys.getsizeof(str(result)) / 1024  # KB
        except:
            return 0.0

    def _record_metric(self, component_name: str, operation: str, execution_time: float):
        """Record performance metric"""
        metric = PerformanceMetric(
            component_name=component_name,
            operation=operation,
            execution_time=execution_time,
            memory_usage=self._get_memory_usage(),
            cpu_usage=self._get_cpu_usage(),
            timestamp=time.time(),
            optimization_applied=True
        )
        self.performance_metrics.append(metric)

        # Keep only recent metrics to avoid memory growth
        if len(self.performance_metrics) > 1000:
            self.performance_metrics = self.performance_metrics[-500:]

    def _get_cpu_usage(self) -> float:
        """Get current CPU usage (simplified)"""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance report"""
        if not self.performance_metrics:
            return {"message": "No performance metrics recorded yet"}

        # Calculate averages
        total_time = sum(m.execution_time for m in self.performance_metrics)
        avg_time = total_time / len(self.performance_metrics) if self.performance_metrics else 0

        total_memory = sum(m.memory_usage for m in self.performance_metrics)
        avg_memory = total_memory / len(self.performance_metrics) if self.performance_metrics else 0

        total_cpu = sum(m.cpu_usage for m in self.performance_metrics)
        avg_cpu = total_cpu / len(self.performance_metrics) if self.performance_metrics else 0

        # Group by component
        component_stats = {}
        for metric in self.performance_metrics:
            if metric.component_name not in component_stats:
                component_stats[metric.component_name] = {
                    'count': 0,
                    'total_time': 0,
                    'avg_time': 0,
                    'operations': set()
                }
            component_stats[metric.component_name]['count'] += 1
            component_stats[metric.component_name]['total_time'] += metric.execution_time
            component_stats[metric.component_name]['operations'].add(metric.operation)

        # Calculate averages per component
        for comp_name, stats in component_stats.items():
            stats['avg_time'] = stats['total_time'] / stats['count']

        return {
            'total_operations': len(self.performance_metrics),
            'average_execution_time': avg_time,
            'average_memory_usage': avg_memory,
            'average_cpu_usage': avg_cpu,
            'component_statistics': component_stats,
            'cache_stats': self.cache_manager.get_stats(),
            'resource_usage': self.component_resources
        }

    def optimize_parallel_execution(self, tasks: List[Callable]) -> Callable:
        """Optimize execution of multiple tasks in parallel"""
        async def execute_parallel():
            if self.optimization_level == OptimizationLevel.LIGHT:
                # Execute sequentially for simplicity
                results = []
                for task in tasks:
                    result = await task()
                    results.append(result)
                return results
            else:
                # Execute in parallel with resource management
                semaphore = asyncio.Semaphore(5)  # Limit concurrent tasks

                async def limited_task(task):
                    async with semaphore:
                        return await task()

                coroutines = [limited_task(task) for task in tasks]
                return await asyncio.gather(*coroutines, return_exceptions=True)

        return execute_parallel


class VLAPerformanceOptimizer:
    """
    Main optimizer for the VLA system
    Applies optimizations to all VLA components
    """

    def __init__(self, optimization_level: OptimizationLevel = OptimizationLevel.MEDIUM):
        self.optimizer = ResourceOptimizer(optimization_level)
        self.logger = logging.getLogger(__name__)
        self.component_optimizers = {}

    def optimize_llm_component(self, llm_manager):
        """Optimize LLM component"""
        # Optimize planning method
        original_plan = llm_manager.plan_action_sequence
        optimized_plan = self.optimizer.optimize_computational_resources(
            "llm_planning", original_plan
        )
        llm_manager.plan_action_sequence = optimized_plan

        # Optimize validation method
        original_validate = llm_manager.validate_plan
        optimized_validate = self.optimizer.optimize_computational_resources(
            "llm_validation", original_validate
        )
        llm_manager.validate_plan = optimized_validate

        # Optimize memory usage for large prompts
        original_methods = ['plan_action_sequence', 'validate_plan']
        for method_name in original_methods:
            if hasattr(llm_manager, method_name):
                original_method = getattr(llm_manager, method_name)
                optimized_method = self.optimizer.optimize_memory_usage(
                    "llm_component", original_method
                )
                setattr(llm_manager, method_name, optimized_method)

        self.logger.info("LLM component optimized", extra={'optimization_level': self.optimizer.optimization_level.value})

    def optimize_speech_component(self, speech_manager):
        """Optimize speech recognition component"""
        # Optimize transcription method
        if hasattr(speech_manager, 'transcribe_audio'):
            original_transcribe = speech_manager.transcribe_audio
            optimized_transcribe = self.optimizer.optimize_computational_resources(
                "speech_transcription", original_transcribe
            )
            speech_manager.transcribe_audio = optimized_transcribe

        # Optimize memory usage for audio processing
        if hasattr(speech_manager, 'transcribe_audio'):
            original_transcribe = speech_manager.transcribe_audio
            optimized_transcribe = self.optimizer.optimize_memory_usage(
                "speech_component", original_transcribe
            )
            speech_manager.transcribe_audio = optimized_transcribe

        self.logger.info("Speech component optimized", extra={'optimization_level': self.optimizer.optimization_level.value})

    def optimize_vision_component(self, vision_component):
        """Optimize vision component"""
        # Optimize object detection
        if hasattr(vision_component, 'detect_objects'):
            original_detect = vision_component.detect_objects
            optimized_detect = self.optimizer.optimize_computational_resources(
                "vision_detection", original_detect
            )
            vision_component.detect_objects = optimized_detect

        # Optimize memory usage for image processing
        if hasattr(vision_component, 'detect_objects'):
            original_detect = vision_component.detect_objects
            optimized_detect = self.optimizer.optimize_memory_usage(
                "vision_component", original_detect
            )
            vision_component.detect_objects = optimized_detect

        self.logger.info("Vision component optimized", extra={'optimization_level': self.optimizer.optimization_level.value})

    def optimize_hri_component(self, hri_component):
        """Optimize Human-Robot Interaction component"""
        # Optimize conversational flow
        if hasattr(hri_component, 'process_user_input'):
            original_process = hri_component.process_user_input
            optimized_process = self.optimizer.optimize_computational_resources(
                "hri_processing", original_process
            )
            hri_component.process_user_input = optimized_process

        # Optimize memory usage for context management
        if hasattr(hri_component, 'process_user_input'):
            original_process = hri_component.process_user_input
            optimized_process = self.optimizer.optimize_memory_usage(
                "hri_component", original_process
            )
            hri_component.process_user_input = optimized_process

        self.logger.info("HRI component optimized", extra={'optimization_level': self.optimizer.optimization_level.value})

    def optimize_all_components(self, vla_system):
        """Optimize all components in the VLA system"""
        try:
            # Optimize each component if it exists
            if hasattr(vla_system, 'llm_manager'):
                self.optimize_llm_component(vla_system.llm_manager)

            if hasattr(vla_system, 'speech_manager'):
                self.optimize_speech_component(vla_system.speech_manager)

            if hasattr(vla_system, 'object_detection'):
                self.optimize_vision_component(vla_system.object_detection)

            if hasattr(vla_system, 'conversational_flow'):
                self.optimize_hri_component(vla_system.conversational_flow)

            # Optimize the main VLA loop
            if hasattr(vla_system, 'vla_loop'):
                self._optimize_vla_loop(vla_system.vla_loop)

            self.logger.info("All VLA components optimized", extra={
                'optimization_level': self.optimizer.optimization_level.value,
                'components_optimized': len([c for c in dir(vla_system) if not c.startswith('_')])
            })

        except Exception as e:
            self.logger.error(f"Error optimizing VLA components: {e}")
            raise

    def _optimize_vla_loop(self, vla_loop):
        """Optimize the main VLA loop"""
        if hasattr(vla_loop, 'process_command'):
            original_process = vla_loop.process_command
            optimized_process = self.optimizer.optimize_computational_resources(
                "vla_loop", original_process
            )
            vla_loop.process_command = optimized_process

        self.logger.info("VLA loop optimized", extra={'optimization_level': self.optimizer.optimization_level.value})

    def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report"""
        return self.optimizer.get_performance_report()

    def apply_runtime_optimizations(self, component_name: str, operation: Callable) -> Callable:
        """Apply runtime optimizations to a specific operation"""
        # Computational optimization
        optimized = self.optimizer.optimize_computational_resources(component_name, operation)

        # Memory optimization
        optimized = self.optimizer.optimize_memory_usage(component_name, optimized)

        # Network optimization (if applicable)
        optimized = self.optimizer.optimize_network_usage(component_name, optimized)

        return optimized


class PerformanceMonitor:
    """
    Monitors performance across VLA system
    Provides real-time performance metrics and alerts
    """

    def __init__(self):
        self.metrics_queue = queue.Queue()
        self.alerts = []
        self.performance_thresholds = {
            'execution_time': 5.0,  # seconds
            'memory_usage': 1000.0,  # MB
            'cpu_usage': 90.0  # percentage
        }
        self.logger = logging.getLogger(__name__)

    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric"""
        try:
            self.metrics_queue.put_nowait(metric)
        except queue.Full:
            # If queue is full, remove oldest and add new
            try:
                self.metrics_queue.get_nowait()
                self.metrics_queue.put_nowait(metric)
            except queue.Empty:
                pass

    def check_thresholds(self, metric: PerformanceMetric) -> List[str]:
        """Check if metric exceeds performance thresholds"""
        alerts = []

        if metric.execution_time > self.performance_thresholds['execution_time']:
            alerts.append(f"Execution time {metric.execution_time:.2f}s exceeds threshold {self.performance_thresholds['execution_time']}s")

        if metric.memory_usage > self.performance_thresholds['memory_usage']:
            alerts.append(f"Memory usage {metric.memory_usage:.2f}MB exceeds threshold {self.performance_thresholds['memory_usage']}MB")

        if metric.cpu_usage > self.performance_thresholds['cpu_usage']:
            alerts.append(f"CPU usage {metric.cpu_usage:.1f}% exceeds threshold {self.performance_thresholds['cpu_usage']}%")

        if alerts:
            self.alerts.extend(alerts)
            for alert in alerts:
                self.logger.warning(f"Performance alert: {alert}")

        return alerts

    def get_current_metrics(self) -> List[PerformanceMetric]:
        """Get current performance metrics"""
        metrics = []
        try:
            while True:
                metric = self.metrics_queue.get_nowait()
                metrics.append(metric)
        except queue.Empty:
            pass

        return metrics

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        metrics = self.get_current_metrics()

        if not metrics:
            return {"message": "No performance metrics available"}

        # Calculate summary statistics
        execution_times = [m.execution_time for m in metrics]
        memory_usages = [m.memory_usage for m in metrics]
        cpu_usages = [m.cpu_usage for m in metrics]

        return {
            'total_metrics': len(metrics),
            'average_execution_time': sum(execution_times) / len(execution_times),
            'average_memory_usage': sum(memory_usages) / len(memory_usages),
            'average_cpu_usage': sum(cpu_usages) / len(cpu_usages),
            'max_execution_time': max(execution_times),
            'max_memory_usage': max(memory_usages),
            'max_cpu_usage': max(cpu_usages),
            'recent_alerts': self.alerts[-10:],  # Last 10 alerts
            'alert_count': len(self.alerts)
        }


# Example usage and testing
async def test_performance_optimization():
    """Test the performance optimization system"""
    print("Testing Performance Optimization System")
    print("=" * 45)

    optimizer = VLAPerformanceOptimizer(OptimizationLevel.MEDIUM)
    monitor = PerformanceMonitor()

    print(f"\n1. Optimization Level: {optimizer.optimizer.optimization_level.value}")
    print(f"   Cache Manager: Initialized with max_size=1000, ttl=300s")
    print(f"   Thread Pool: Created with 4 workers")

    # Simulate performance metrics
    print(f"\n2. Simulating performance metrics...")
    for i in range(10):
        metric = PerformanceMetric(
            component_name=f"component_{i % 3}",
            operation=f"operation_{i % 2}",
            execution_time=0.1 + (i * 0.01),
            memory_usage=50.0 + (i * 5.0),
            cpu_usage=20.0 + (i * 2.0),
            timestamp=time.time()
        )
        monitor.record_metric(metric)

        # Check thresholds
        alerts = monitor.check_thresholds(metric)
        if alerts:
            print(f"   Alert {i+1}: {alerts[0][:50]}...")

    print(f"   ✓ Recorded 10 performance metrics")

    # Show performance summary
    print(f"\n3. Performance Summary:")
    summary = monitor.get_performance_summary()
    print(f"   Total Metrics: {summary['total_metrics']}")
    print(f"   Avg Execution Time: {summary['average_execution_time']:.3f}s")
    print(f"   Avg Memory Usage: {summary['average_memory_usage']:.1f}MB")
    print(f"   Avg CPU Usage: {summary['average_cpu_usage']:.1f}%")
    print(f"   Alerts Generated: {summary['alert_count']}")

    # Show optimization report
    print(f"\n4. Optimization Report:")
    report = optimizer.get_optimization_report()
    if 'total_operations' in report:
        print(f"   Total Operations: {report['total_operations']}")
        print(f"   Avg Execution Time: {report['average_execution_time']:.3f}s")
        print(f"   Avg Memory Usage: {report['average_memory_usage']:.1f}MB")
        print(f"   Avg CPU Usage: {report['average_cpu_usage']:.1f}%")
    else:
        print(f"   {report['message']}")

    # Show cache statistics
    cache_stats = optimizer.optimizer.cache_manager.get_stats()
    print(f"\n5. Cache Statistics:")
    print(f"   Current Size: {cache_stats['size']}/{cache_stats['max_size']}")
    print(f"   Active Entries: {cache_stats['active_entries']}")
    print(f"   Expired Entries: {cache_stats['expired_entries']}")

    print(f"\nPerformance optimization system test completed!")


def explain_optimization_strategies():
    """Explain the optimization strategies used in the VLA system"""
    print("\nVLA System Optimization Strategies")
    print("=" * 45)

    strategies = {
        "Caching": {
            "description": "Store frequently accessed results to avoid recomputation",
            "benefits": [
                "Reduced computation time",
                "Lower resource usage",
                "Faster response times"
            ],
            "implementation": "LRU cache with TTL for VLA components"
        },
        "Parallel Processing": {
            "description": "Execute independent operations concurrently",
            "benefits": [
                "Improved throughput",
                "Better resource utilization",
                "Reduced overall execution time"
            ],
            "implementation": "AsyncIO with semaphores and thread pools"
        },
        "Resource Pooling": {
            "description": "Reuse expensive resources like connections and models",
            "benefits": [
                "Reduced initialization overhead",
                "Better memory management",
                "Faster operation startup"
            ],
            "implementation": "Connection pools and model caching"
        },
        "Lazy Loading": {
            "description": "Load resources only when needed",
            "benefits": [
                "Reduced startup time",
                "Lower memory footprint",
                "On-demand resource allocation"
            ],
            "implementation": "Deferred model loading and component initialization"
        },
        "Memory Management": {
            "description": "Optimize memory usage and prevent leaks",
            "benefits": [
                "Stable performance over time",
                "Prevention of out-of-memory errors",
                "Efficient resource utilization"
            ],
            "implementation": "Memory monitoring and garbage collection optimization"
        },
        "Computational Optimization": {
            "description": "Optimize algorithms and computations",
            "benefits": [
                "Faster execution",
                "Lower CPU usage",
                "Improved responsiveness"
            ],
            "implementation": "Algorithm optimization and efficient data structures"
        }
    }

    for strategy_name, strategy_info in strategies.items():
        print(f"\n{strategy_name}:")
        print(f"  Description: {strategy_info['description']}")
        print(f"  Benefits:")
        for benefit in strategy_info['benefits']:
            print(f"    • {benefit}")
        print(f"  Implementation: {strategy_info['implementation']}")

    print(f"\nOptimization Levels:")
    optimization_levels = {
        "Light": "Minimal optimization, prioritizing simplicity and reliability",
        "Medium": "Balanced optimization with caching and basic parallelization",
        "Aggressive": "Maximum optimization with extensive caching and parallel processing"
    }

    for level, description in optimization_levels.items():
        print(f"  {level}: {description}")

    print(f"\nPerformance Benefits:")
    benefits = [
        "Faster command processing and response times",
        "Reduced computational resource usage",
        "Lower memory consumption",
        "Improved system throughput",
        "Enhanced user experience with quicker responses",
        "Better scalability under load",
        "More efficient use of robot computational resources"
    ]

    for benefit in benefits:
        print(f"  ✓ {benefit}")


if __name__ == "__main__":
    # Run the performance optimization test
    asyncio.run(test_performance_optimization())

    # Explain the optimization strategies
    explain_optimization_strategies()