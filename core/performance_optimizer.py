"""
Performance Optimization System
Provides caching layer, database optimization, memory management, and async improvements.
"""

import asyncio
import gc
import psutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging
import pickle
import hashlib
import json
from pathlib import Path
import weakref
import functools
from contextlib import asynccontextmanager, contextmanager

@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 0
    hit_rate: float = 0.0
    evictions: int = 0
    memory_usage_mb: float = 0.0

@dataclass
class DatabaseStats:
    """Database performance statistics"""
    total_queries: int = 0
    slow_queries: int = 0
    average_query_time: float = 0.0
    connection_pool_size: int = 0
    active_connections: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_memory_mb: float = 0.0
    available_memory_mb: float = 0.0
    used_memory_mb: float = 0.0
    memory_percent: float = 0.0
    gc_collections: Dict[int, int] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """Overall performance metrics"""
    cache_stats: CacheStats = field(default_factory=CacheStats)
    database_stats: DatabaseStats = field(default_factory=DatabaseStats)
    memory_stats: MemoryStats = field(default_factory=MemoryStats)
    cpu_percent: float = 0.0
    disk_usage_percent: float = 0.0
    network_io: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

class LRUCache:
    """High-performance LRU cache with TTL support"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: Optional[int] = None):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self.access_times = {}
        self.stats = CacheStats(max_size=max_size)
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Any:
        """Get value from cache"""
        with self.lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            # Check TTL
            if self.ttl_seconds and self._is_expired(key):
                del self.cache[key]
                del self.access_times[key]
                self.stats.misses += 1
                self.stats.size -= 1
                return None
            
            # Move to end (most recently used)
            value = self.cache.pop(key)
            self.cache[key] = value
            self.access_times[key] = time.time()
            
            self.stats.hits += 1
            self._update_hit_rate()
            
            return value
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        with self.lock:
            # Remove if already exists
            if key in self.cache:
                del self.cache[key]
                self.stats.size -= 1
            
            # Evict if at capacity
            while len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
                self.stats.evictions += 1
                self.stats.size -= 1
            
            # Add new value
            self.cache[key] = value
            self.access_times[key] = time.time()
            self.stats.size += 1
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.access_times[key]
                self.stats.size -= 1
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.stats.size = 0
    
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired"""
        if not self.ttl_seconds:
            return False
        
        access_time = self.access_times.get(key, 0)
        return time.time() - access_time > self.ttl_seconds
    
    def _update_hit_rate(self):
        """Update cache hit rate"""
        total_requests = self.stats.hits + self.stats.misses
        if total_requests > 0:
            self.stats.hit_rate = self.stats.hits / total_requests
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count"""
        if not self.ttl_seconds:
            return 0
        
        expired_count = 0
        current_time = time.time()
        
        with self.lock:
            expired_keys = [
                key for key, access_time in self.access_times.items()
                if current_time - access_time > self.ttl_seconds
            ]
            
            for key in expired_keys:
                del self.cache[key]
                del self.access_times[key]
                expired_count += 1
                self.stats.size -= 1
        
        return expired_count

class AsyncCache:
    """Async-compatible cache wrapper"""
    
    def __init__(self, cache: LRUCache):
        self.cache = cache
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Any:
        """Async get from cache"""
        # LRU cache is thread-safe, so we can call directly
        return self.cache.get(key)
    
    async def set(self, key: str, value: Any) -> None:
        """Async set to cache"""
        self.cache.set(key, value)
    
    async def delete(self, key: str) -> bool:
        """Async delete from cache"""
        return self.cache.delete(key)

class DatabaseOptimizer:
    """Database-specific performance optimization"""
    
    def __init__(self, pool_size: int = 10):
        from core.database_config import DatabaseConfig
        
        self.database_config = DatabaseConfig
        self.is_postgresql = DatabaseConfig.is_postgresql()
        self.connection_pool = []
        self.pool_size = pool_size
        self.pool_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.stats = DatabaseStats()
        self.slow_query_threshold = 1.0  # seconds
        
        # Initialize cache for query results
        self.query_cache = LRUCache(max_size=500, ttl_seconds=300)
        
        # Initialize connection pool
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize database connection pool"""
        with self.pool_lock:
            for _ in range(self.pool_size):
                if self.is_postgresql:
                    import psycopg2
                    params = self.database_config.get_raw_connection_params()
                    conn = psycopg2.connect(
                        host=params['host'],
                        port=params['port'],
                        database=params['database'],
                        user=params['user'],
                        password=params['password'],
                        connect_timeout=30
                    )
                    conn.autocommit = False
                else:
                    import sqlite3
                    params = self.database_config.get_raw_connection_params()
                    conn = sqlite3.connect(
                        params['database'],
                        check_same_thread=False,
                        timeout=30
                    )
                    conn.row_factory = sqlite3.Row
                    # Enable WAL mode for better concurrency (SQLite only)
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA cache_size=10000")
                    conn.execute("PRAGMA temp_store=MEMORY")
                
                self.connection_pool.append(conn)
    
    @contextmanager
    def get_connection(self):
        """Get database connection from pool"""
        conn = None
        try:
            with self.pool_lock:
                if self.connection_pool:
                    conn = self.connection_pool.pop()
                    self.stats.active_connections += 1
                else:
                    # Pool exhausted, create temporary connection
                    if self.is_postgresql:
                        import psycopg2
                        params = self.database_config.get_raw_connection_params()
                        conn = psycopg2.connect(
                            host=params['host'],
                            port=params['port'],
                            database=params['database'],
                            user=params['user'],
                            password=params['password'],
                            connect_timeout=30
                        )
                    else:
                        import sqlite3
                        params = self.database_config.get_raw_connection_params()
                        conn = sqlite3.connect(
                            params['database'],
                            check_same_thread=False,
                            timeout=30
                        )
                        conn.row_factory = sqlite3.Row
            
            yield conn
            
        finally:
            if conn:
                with self.pool_lock:
                    if len(self.connection_pool) < self.pool_size:
                        self.connection_pool.append(conn)
                        self.stats.active_connections -= 1
                    else:
                        conn.close()
    
    def execute_query(self, query: str, params: tuple = (), use_cache: bool = True) -> list:
        """Execute query with caching and performance monitoring"""
        start_time = time.time()
        
        # Generate cache key
        cache_key = None
        if use_cache and query.strip().upper().startswith('SELECT'):
            cache_key = hashlib.md5(f"{query}{params}".encode()).hexdigest()
            cached_result = self.query_cache.get(cache_key)
            if cached_result is not None:
                self.stats.cache_hits += 1
                return cached_result
        
        # Execute query
        try:
            with self.get_connection() as conn:
                if self.is_postgresql:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchall()
                    cursor.close()
                else:
                    cursor = conn.execute(query, params)
                    result = cursor.fetchall()
                
                # Cache SELECT results
                if cache_key:
                    self.query_cache.set(cache_key, result)
                    self.stats.cache_misses += 1
                
                # Update statistics
                query_time = time.time() - start_time
                self.stats.total_queries += 1
                
                if query_time > self.slow_query_threshold:
                    self.stats.slow_queries += 1
                    self.logger.warning(f"Slow query ({query_time:.2f}s): {query[:100]}...")
                
                # Update average query time
                total_time = self.stats.average_query_time * (self.stats.total_queries - 1)
                self.stats.average_query_time = (total_time + query_time) / self.stats.total_queries
                
                return result
                
        except Exception as e:
            self.logger.error(f"Database query failed: {e}")
            raise
    
    def execute_transaction(self, queries: List[Tuple[str, Tuple]], use_cache: bool = False):
        """Execute multiple queries in a transaction"""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                
                for query, params in queries:
                    conn.execute(query, params)
                
                conn.execute("COMMIT")
                
            except Exception as e:
                conn.execute("ROLLBACK")
                self.logger.error(f"Transaction failed: {e}")
                raise
    
    def optimize_database(self):
        """Run database optimization tasks"""
        with self.get_connection() as conn:
            if self.is_postgresql:
                # PostgreSQL optimization
                cursor = conn.cursor()
                cursor.execute("ANALYZE")
                conn.commit()
                cursor.close()
                self.logger.info("PostgreSQL ANALYZE completed")
            else:
                # SQLite optimization
                conn.execute("ANALYZE")
                
                # Vacuum if needed (reclaim space)
                vacuum_threshold = 1000000  # 1MB
                page_count = conn.execute("PRAGMA page_count").fetchone()[0]
                page_size = conn.execute("PRAGMA page_size").fetchone()[0]
                db_size = page_count * page_size
                
                if db_size > vacuum_threshold:
                    conn.execute("VACUUM")
                    self.logger.info("SQLite vacuum completed")
    
    def get_database_size(self) -> int:
        """Get database size in bytes"""
        if self.is_postgresql:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT pg_database_size(current_database())")
                size = cursor.fetchone()[0]
                cursor.close()
                return size
        else:
            from pathlib import Path
            params = self.database_config.get_raw_connection_params()
            return Path(params['database']).stat().st_size

class MemoryManager:
    """Memory usage monitoring and optimization"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.memory_threshold = 80.0  # Trigger cleanup at 80% memory usage
        self.gc_enabled = True
        self.weak_refs = weakref.WeakSet()
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics"""
        memory = psutil.virtual_memory()
        
        gc_stats = {}
        for i in range(3):
            gc_stats[i] = gc.get_count()[i]
        
        return MemoryStats(
            total_memory_mb=memory.total / 1024 / 1024,
            available_memory_mb=memory.available / 1024 / 1024,
            used_memory_mb=memory.used / 1024 / 1024,
            memory_percent=memory.percent,
            gc_collections=gc_stats
        )
    
    def monitor_memory(self) -> bool:
        """Monitor memory usage and trigger cleanup if needed"""
        stats = self.get_memory_stats()
        
        if stats.memory_percent > self.memory_threshold:
            self.logger.warning(f"High memory usage: {stats.memory_percent:.1f}%")
            self.cleanup_memory()
            return True
        
        return False
    
    def cleanup_memory(self):
        """Perform memory cleanup"""
        if self.gc_enabled:
            # Force garbage collection
            collected = gc.collect()
            self.logger.info(f"Garbage collection freed {collected} objects")
        
        # Clear weak references
        self.weak_refs.clear()
    
    def register_for_cleanup(self, obj: Any):
        """Register object for cleanup tracking"""
        try:
            self.weak_refs.add(obj)
        except TypeError:
            # Object doesn't support weak references, track normally
            if not hasattr(self, '_strong_refs'):
                self._strong_refs = set()
            self._strong_refs.add(id(obj))

class AsyncTaskManager:
    """Manages async tasks and thread pools for performance"""
    
    def __init__(self, max_threads: int = 10, max_processes: int = None):
        self.max_threads = max_threads
        self.max_processes = max_processes or min(4, psutil.cpu_count())
        self.thread_executor = ThreadPoolExecutor(max_workers=max_threads)
        self.process_executor = ProcessPoolExecutor(max_workers=self.max_processes)
        self.logger = logging.getLogger(__name__)
        
        # Task tracking
        self.active_tasks = {}
        self.completed_tasks = 0
        self.failed_tasks = 0
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run function in thread pool"""
        loop = asyncio.get_event_loop()
        
        task_id = id((func, args, kwargs))
        self.active_tasks[task_id] = {
            'func': func.__name__,
            'start_time': time.time(),
            'type': 'thread'
        }
        
        try:
            result = await loop.run_in_executor(
                self.thread_executor, 
                functools.partial(func, *args, **kwargs)
            )
            self.completed_tasks += 1
            return result
            
        except Exception as e:
            self.failed_tasks += 1
            self.logger.error(f"Thread task failed: {e}")
            raise
        finally:
            self.active_tasks.pop(task_id, None)
    
    async def run_in_process(self, func: Callable, *args, **kwargs) -> Any:
        """Run function in process pool"""
        loop = asyncio.get_event_loop()
        
        task_id = id((func, args, kwargs))
        self.active_tasks[task_id] = {
            'func': func.__name__,
            'start_time': time.time(),
            'type': 'process'
        }
        
        try:
            result = await loop.run_in_executor(
                self.process_executor,
                functools.partial(func, *args, **kwargs)
            )
            self.completed_tasks += 1
            return result
            
        except Exception as e:
            self.failed_tasks += 1
            self.logger.error(f"Process task failed: {e}")
            raise
        finally:
            self.active_tasks.pop(task_id, None)
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task execution statistics"""
        return {
            'active_tasks': len(self.active_tasks),
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'thread_pool_size': self.max_threads,
            'process_pool_size': self.max_processes,
            'active_task_details': [
                {
                    'func': task['func'],
                    'runtime': time.time() - task['start_time'],
                    'type': task['type']
                }
                for task in self.active_tasks.values()
            ]
        }
    
    def shutdown(self):
        """Shutdown executors"""
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)

class PerformanceOptimizer:
    """Main performance optimization system"""
    
    def __init__(self, cache_size: int = 1000):
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.cache = LRUCache(max_size=cache_size, ttl_seconds=3600)  # 1 hour TTL
        self.async_cache = AsyncCache(self.cache)
        self.db_optimizer = DatabaseOptimizer(10)
        self.memory_manager = MemoryManager()
        self.task_manager = AsyncTaskManager()
        
        # Monitoring
        self.metrics = PerformanceMetrics()
        self.monitoring_interval = 60  # seconds
        self.monitoring_task = None
        
        # Optimization settings
        self.auto_optimize = True
        self.optimization_interval = 3600  # 1 hour
        self.last_optimization = time.time()
    
    def start_monitoring(self):
        """Start performance monitoring"""
        if self.monitoring_task is None:
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None
            self.logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self.update_metrics()
                
                # Auto-optimization
                if self.auto_optimize:
                    if time.time() - self.last_optimization > self.optimization_interval:
                        await self.optimize_performance()
                        self.last_optimization = time.time()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def update_metrics(self):
        """Update performance metrics"""
        # Cache stats
        self.metrics.cache_stats = CacheStats(
            hits=self.cache.stats.hits,
            misses=self.cache.stats.misses,
            size=self.cache.stats.size,
            max_size=self.cache.stats.max_size,
            hit_rate=self.cache.stats.hit_rate,
            evictions=self.cache.stats.evictions,
            memory_usage_mb=self._estimate_cache_memory()
        )
        
        # Database stats
        self.metrics.database_stats = self.db_optimizer.stats
        
        # Memory stats
        self.metrics.memory_stats = self.memory_manager.get_memory_stats()
        
        # System stats
        self.metrics.cpu_percent = psutil.cpu_percent()
        self.metrics.disk_usage_percent = psutil.disk_usage('/').percent
        
        # Network I/O
        net_io = psutil.net_io_counters()
        self.metrics.network_io = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv
        }
        
        self.metrics.last_updated = datetime.now()
    
    def _estimate_cache_memory(self) -> float:
        """Estimate cache memory usage in MB"""
        try:
            # Rough estimate based on cache size
            # This is approximate since Python object sizes vary
            estimated_bytes = len(self.cache.cache) * 1024  # Assume 1KB per entry average
            return estimated_bytes / 1024 / 1024
        except:
            return 0.0
    
    async def optimize_performance(self):
        """Run performance optimizations"""
        self.logger.info("Running performance optimization")
        
        # Cache optimization
        expired_count = self.cache.cleanup_expired()
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired cache entries")
        
        # Database optimization
        await self.task_manager.run_in_thread(self.db_optimizer.optimize_database)
        
        # Memory optimization
        if self.memory_manager.monitor_memory():
            self.logger.info("Memory cleanup performed")
        
        # Clear old database query cache
        self.db_optimizer.query_cache.cleanup_expired()
        
        self.logger.info("Performance optimization completed")
    
    # Cache interface methods
    async def cache_get(self, key: str) -> Any:
        """Get value from cache"""
        return await self.async_cache.get(key)
    
    async def cache_set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        await self.async_cache.set(key, value)
    
    async def cache_delete(self, key: str) -> bool:
        """Delete value from cache"""
        return await self.async_cache.delete(key)
    
    # Database interface methods
    async def db_query(self, query: str, params: Tuple = (), use_cache: bool = True) -> List[sqlite3.Row]:
        """Execute database query with optimization"""
        return await self.task_manager.run_in_thread(
            self.db_optimizer.execute_query, query, params, use_cache
        )
    
    async def db_transaction(self, queries: List[Tuple[str, Tuple]]):
        """Execute database transaction"""
        return await self.task_manager.run_in_thread(
            self.db_optimizer.execute_transaction, queries
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        return {
            'cache': {
                'hit_rate': self.metrics.cache_stats.hit_rate,
                'size': self.metrics.cache_stats.size,
                'memory_usage_mb': self.metrics.cache_stats.memory_usage_mb
            },
            'database': {
                'total_queries': self.metrics.database_stats.total_queries,
                'slow_queries': self.metrics.database_stats.slow_queries,
                'average_query_time': self.metrics.database_stats.average_query_time,
                'cache_hit_rate': (
                    self.metrics.database_stats.cache_hits / 
                    max(1, self.metrics.database_stats.cache_hits + self.metrics.database_stats.cache_misses)
                )
            },
            'memory': {
                'usage_percent': self.metrics.memory_stats.memory_percent,
                'available_mb': self.metrics.memory_stats.available_memory_mb
            },
            'system': {
                'cpu_percent': self.metrics.cpu_percent,
                'disk_usage_percent': self.metrics.disk_usage_percent
            },
            'tasks': self.task_manager.get_task_stats(),
            'last_updated': self.metrics.last_updated.isoformat()
        }
    
    def shutdown(self):
        """Shutdown performance optimizer"""
        self.stop_monitoring()
        self.task_manager.shutdown()
        self.logger.info("Performance optimizer shut down")


# Global performance optimizer
_performance_optimizer: Optional[PerformanceOptimizer] = None

def get_performance_optimizer(cache_size: int = 1000) -> PerformanceOptimizer:
    """Get performance optimizer instance"""
    return PerformanceOptimizer(cache_size=cache_size)

# Decorators for performance optimization
def cached(ttl_seconds: int = 3600, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()
            
            # Generate cache key
            key_parts = [key_prefix, func.__name__, str(args), str(sorted(kwargs.items()))]
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
            
            # Try cache first
            cached_result = await optimizer.cache_get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Cache the result
            await optimizer.cache_set(cache_key, result)
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run async wrapper in event loop
            async def cache_wrapper():
                return await async_wrapper(*args, **kwargs)
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(cache_wrapper())
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def db_optimized(use_cache: bool = True):
    """Decorator for database query optimization"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            optimizer = get_performance_optimizer()
            
            # If function returns query and params, execute optimized
            result = await func(*args, **kwargs)
            
            if isinstance(result, tuple) and len(result) == 2:
                query, params = result
                return await optimizer.db_query(query, params, use_cache)
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # Convert sync function to async
            @functools.wraps(func)
            async def sync_to_async_wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return async_wrapper
    
    return decorator 