"""
Test suite for Performance Optimization System
Tests caching, database optimization, memory management, and async improvements.
"""

import pytest
import asyncio
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.performance_optimizer import (
    LRUCache, AsyncCache, DatabaseOptimizer, MemoryManager,
    AsyncTaskManager, PerformanceOptimizer,
    CacheStats, DatabaseStats, MemoryStats, PerformanceMetrics,
    get_performance_optimizer, cached, db_optimized
)

class TestLRUCache:
    """Test LRUCache class"""
    
    def test_cache_creation(self):
        """Test creating LRU cache"""
        cache = LRUCache(max_size=100, ttl_seconds=3600)
        assert cache.max_size == 100
        assert cache.ttl_seconds == 3600
        assert len(cache.cache) == 0
        assert cache.stats.max_size == 100
    
    def test_cache_set_get(self):
        """Test basic cache set/get operations"""
        cache = LRUCache(max_size=3)
        
        # Set values
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # Get values
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        
        # Check stats
        assert cache.stats.size == 3
        assert cache.stats.hits == 3
        assert cache.stats.misses == 0
    
    def test_cache_eviction(self):
        """Test cache eviction when max size reached"""
        cache = LRUCache(max_size=2)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        
        assert cache.stats.evictions == 1
        assert cache.stats.size == 2
    
    def test_cache_lru_order(self):
        """Test LRU ordering"""
        cache = LRUCache(max_size=2)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Access key1 to make it most recently used
        cache.get("key1")
        
        # Add key3, should evict key2 (least recently used)
        cache.set("key3", "value3")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
    
    def test_cache_ttl(self):
        """Test cache TTL functionality"""
        cache = LRUCache(max_size=10, ttl_seconds=1)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Simulate TTL expiry
        cache.access_times["key1"] = time.time() - 2
        
        assert cache.get("key1") is None  # Should be expired
        assert cache.stats.size == 0
    
    def test_cache_delete(self):
        """Test cache delete operation"""
        cache = LRUCache(max_size=10)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        assert cache.delete("key1") == True
        assert cache.get("key1") is None
        assert cache.delete("nonexistent") == False
    
    def test_cache_clear(self):
        """Test cache clear operation"""
        cache = LRUCache(max_size=10)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.stats.size == 0
    
    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries"""
        cache = LRUCache(max_size=10, ttl_seconds=1)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Expire key1
        cache.access_times["key1"] = time.time() - 2
        
        expired_count = cache.cleanup_expired()
        
        assert expired_count == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestAsyncCache:
    """Test AsyncCache class"""
    
    @pytest.mark.asyncio
    async def test_async_cache_operations(self):
        """Test async cache operations"""
        lru_cache = LRUCache(max_size=10)
        async_cache = AsyncCache(lru_cache)
        
        await async_cache.set("key1", "value1")
        value = await async_cache.get("key1")
        assert value == "value1"
        
        deleted = await async_cache.delete("key1")
        assert deleted == True
        
        value = await async_cache.get("key1")
        assert value is None


class TestDatabaseOptimizer:
    """Test DatabaseOptimizer class"""
    
    def setup_method(self):
        """Setup test database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test table
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    value INTEGER
                )
            """)
            
            # Insert test data
            for i in range(10):
                conn.execute(
                    "INSERT INTO test_table (name, value) VALUES (?, ?)",
                    (f"item_{i}", i * 10)
                )
            conn.commit()
    
    def teardown_method(self):
        """Cleanup test database"""
        Path(self.db_path).unlink()
    
    def test_optimizer_creation(self):
        """Test creating database optimizer"""
        optimizer = DatabaseOptimizer(self.db_path, pool_size=5)
        assert optimizer.db_path == self.db_path
        assert optimizer.pool_size == 5
        assert len(optimizer.connection_pool) == 5
    
    def test_execute_query(self):
        """Test executing queries with optimization"""
        optimizer = DatabaseOptimizer(self.db_path, pool_size=2)
        
        # Test SELECT query
        results = optimizer.execute_query("SELECT * FROM test_table WHERE value > ?", (50,))
        assert len(results) >= 4  # Items with value > 50 (flexible count)
        
        # Test cached query
        cached_results = optimizer.execute_query("SELECT * FROM test_table WHERE value > ?", (50,))
        assert len(cached_results) >= 4
        assert optimizer.stats.cache_hits == 1
    
    def test_execute_transaction(self):
        """Test executing transactions"""
        optimizer = DatabaseOptimizer(self.db_path, pool_size=2)
        
        queries = [
            ("INSERT INTO test_table (name, value) VALUES (?, ?)", ("new_item", 999)),
            ("UPDATE test_table SET value = ? WHERE name = ?", (1000, "new_item"))
        ]
        
        optimizer.execute_transaction(queries)
        
        # Verify transaction results
        results = optimizer.execute_query("SELECT value FROM test_table WHERE name = ?", ("new_item",))
        assert len(results) == 1
        assert results[0][0] == 1000
    
    def test_connection_pool(self):
        """Test connection pool management"""
        optimizer = DatabaseOptimizer(self.db_path, pool_size=2)
        
        with optimizer.get_connection() as conn1:
            assert optimizer.stats.active_connections == 1
            
            with optimizer.get_connection() as conn2:
                assert optimizer.stats.active_connections == 2
                
                # Third connection should create temporary connection
                with optimizer.get_connection() as conn3:
                    assert conn3 is not None
        
        # Connections should be returned to pool
        assert optimizer.stats.active_connections == 0
    
    def test_query_performance_tracking(self):
        """Test query performance tracking"""
        optimizer = DatabaseOptimizer(self.db_path, pool_size=2)
        optimizer.slow_query_threshold = 0.001  # Very low threshold
        
        # Execute a query that should be marked as slow
        optimizer.execute_query("SELECT * FROM test_table")
        
        assert optimizer.stats.total_queries == 1
        assert optimizer.stats.average_query_time > 0


class TestMemoryManager:
    """Test MemoryManager class"""
    
    def test_memory_manager_creation(self):
        """Test creating memory manager"""
        manager = MemoryManager()
        assert manager.memory_threshold == 80.0
        assert manager.gc_enabled == True
    
    def test_get_memory_stats(self):
        """Test getting memory statistics"""
        manager = MemoryManager()
        stats = manager.get_memory_stats()
        
        assert isinstance(stats.total_memory_mb, float)
        assert isinstance(stats.available_memory_mb, float)
        assert isinstance(stats.used_memory_mb, float)
        assert isinstance(stats.memory_percent, float)
        assert isinstance(stats.gc_collections, dict)
        
        assert stats.total_memory_mb > 0
        assert stats.memory_percent >= 0
        assert stats.memory_percent <= 100
    
    def test_register_for_cleanup(self):
        """Test registering objects for cleanup"""
        manager = MemoryManager()
        
        test_object = {"data": "test"}
        manager.register_for_cleanup(test_object)
        
        # Dictionary objects can't be weakly referenced, so they're tracked in _strong_refs
        assert hasattr(manager, '_strong_refs')
        assert id(test_object) in manager._strong_refs


# Global function for process pool testing (required for serialization)
def global_test_function(x):
    return x * x

class TestAsyncTaskManager:
    """Test AsyncTaskManager class"""
    
    def test_task_manager_creation(self):
        """Test creating async task manager"""
        manager = AsyncTaskManager(max_threads=5, max_processes=2)
        assert manager.max_threads == 5
        assert manager.max_processes == 2
        assert manager.completed_tasks == 0
        assert manager.failed_tasks == 0
    
    @pytest.mark.asyncio
    async def test_run_in_thread(self):
        """Test running function in thread pool"""
        manager = AsyncTaskManager(max_threads=2)
        
        def test_function(x, y):
            time.sleep(0.1)  # Simulate work
            return x + y
        
        result = await manager.run_in_thread(test_function, 5, 10)
        assert result == 15
        assert manager.completed_tasks == 1
    
    @pytest.mark.asyncio
    async def test_run_in_process(self):
        """Test running function in process pool"""
        manager = AsyncTaskManager(max_processes=2)
        
        result = await manager.run_in_process(global_test_function, 7)
        assert result == 49
        assert manager.completed_tasks == 1
    
    def test_get_task_stats(self):
        """Test getting task statistics"""
        manager = AsyncTaskManager()
        stats = manager.get_task_stats()
        
        assert 'active_tasks' in stats
        assert 'completed_tasks' in stats
        assert 'failed_tasks' in stats
        assert 'thread_pool_size' in stats
        assert 'process_pool_size' in stats
        assert 'active_task_details' in stats


class TestPerformanceOptimizer:
    """Test PerformanceOptimizer class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create test database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    value INTEGER
                )
            """)
            conn.commit()
    
    def teardown_method(self):
        """Cleanup test environment"""
        Path(self.db_path).unlink()
    
    def test_optimizer_creation(self):
        """Test creating performance optimizer"""
        optimizer = PerformanceOptimizer(cache_size=100, db_path=self.db_path)
        
        assert optimizer.cache.max_size == 100
        assert optimizer.db_optimizer.db_path == self.db_path
        assert isinstance(optimizer.memory_manager, MemoryManager)
        assert isinstance(optimizer.task_manager, AsyncTaskManager)
    
    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test cache operations through optimizer"""
        optimizer = PerformanceOptimizer(cache_size=10, db_path=self.db_path)
        
        await optimizer.cache_set("test_key", "test_value")
        value = await optimizer.cache_get("test_key")
        assert value == "test_value"
        
        deleted = await optimizer.cache_delete("test_key")
        assert deleted == True
        
        value = await optimizer.cache_get("test_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_db_operations(self):
        """Test database operations through optimizer"""
        optimizer = PerformanceOptimizer(cache_size=10, db_path=self.db_path)
        
        # Test query
        results = await optimizer.db_query("SELECT name FROM sqlite_master WHERE type='table'")
        assert len(results) > 0
        
        # Test transaction
        queries = [
            ("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test", 123))
        ]
        await optimizer.db_transaction(queries)
        
        # Verify insert
        results = await optimizer.db_query("SELECT * FROM test_table WHERE name = ?", ("test",))
        assert len(results) == 1
        assert results[0][1] == "test"
        assert results[0][2] == 123
    
    @pytest.mark.asyncio
    async def test_update_metrics(self):
        """Test updating performance metrics"""
        optimizer = PerformanceOptimizer(cache_size=10, db_path=self.db_path)
        
        # Add some cache activity
        await optimizer.cache_set("key1", "value1")
        await optimizer.cache_get("key1")
        
        await optimizer.update_metrics()
        
        assert optimizer.metrics.cache_stats.hits > 0
        assert optimizer.metrics.memory_stats.total_memory_mb > 0
        assert optimizer.metrics.cpu_percent >= 0
    
    def test_get_performance_summary(self):
        """Test getting performance summary"""
        optimizer = PerformanceOptimizer(cache_size=10, db_path=self.db_path)
        
        summary = optimizer.get_performance_summary()
        
        assert 'cache' in summary
        assert 'database' in summary
        assert 'memory' in summary
        assert 'system' in summary
        assert 'tasks' in summary
        assert 'last_updated' in summary
        
        # Check cache section
        assert 'hit_rate' in summary['cache']
        assert 'size' in summary['cache']
        assert 'memory_usage_mb' in summary['cache']


class TestDecorators:
    """Test performance optimization decorators"""
    
    def setup_method(self):
        """Setup test environment"""
        # Clear global optimizer
        import core.performance_optimizer
        core.performance_optimizer._performance_optimizer = None
    
    @pytest.mark.asyncio
    async def test_cached_decorator_async(self):
        """Test cached decorator on async function"""
        call_count = 0
        
        @cached(ttl_seconds=3600, key_prefix="test")
        async def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate work
            return x + y
        
        # First call should execute function
        result1 = await expensive_function(5, 10)
        assert result1 == 15
        assert call_count == 1
        
        # Second call should use cache
        result2 = await expensive_function(5, 10)
        assert result2 == 15
        assert call_count == 1  # Should not increment
    
    def test_cached_decorator_sync(self):
        """Test cached decorator on sync function"""
        call_count = 0
        
        @cached(ttl_seconds=3600, key_prefix="test")
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)  # Simulate work
            return x * y
        
        # First call should execute function
        result1 = expensive_function(5, 10)
        assert result1 == 50
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(5, 10)
        assert result2 == 50
        assert call_count == 1  # Should not increment
    
    @pytest.mark.asyncio
    async def test_db_optimized_decorator(self):
        """Test db_optimized decorator"""
        @db_optimized(use_cache=True)
        async def get_query():
            return "SELECT 1", ()
        
        result = await get_query()
        # Should return the query result, not the tuple
        assert len(result) > 0


class TestGlobalFunctions:
    """Test global functions"""
    
    def setup_method(self):
        """Setup test environment"""
        # Clear global optimizer
        import core.performance_optimizer
        core.performance_optimizer._performance_optimizer = None
    
    def test_get_performance_optimizer(self):
        """Test getting global performance optimizer"""
        optimizer1 = get_performance_optimizer(cache_size=100)
        optimizer2 = get_performance_optimizer(cache_size=200)  # Should ignore new params
        
        # Should return same instance (singleton)
        assert optimizer1 is optimizer2
        assert optimizer1.cache.max_size == 100  # Original params


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 