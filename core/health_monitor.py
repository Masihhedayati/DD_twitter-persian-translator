"""
Health Monitoring System for Twitter Monitor Application

This module provides comprehensive health checks, performance monitoring,
and system status tracking for all application components.
"""

import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import sqlite3


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning" 
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    """Individual health metric"""
    name: str
    value: Any
    unit: str
    status: HealthStatus
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""


@dataclass
class ComponentHealth:
    """Health status for a specific component"""
    component_name: str
    status: HealthStatus
    metrics: Dict[str, HealthMetric] = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.now)
    uptime_seconds: float = 0
    error_count: int = 0
    last_error: Optional[str] = None


class HealthMonitor:
    """Comprehensive health monitoring system"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.component_health: Dict[str, ComponentHealth] = {}
        self.system_metrics: Dict[str, HealthMetric] = {}
        self.health_history: List[Dict[str, Any]] = []
        self.running = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        # Register default system checks
        self.health_checks = {
            'cpu_usage': self._check_cpu_usage,
            'memory_usage': self._check_memory_usage,
            'disk_usage': self._check_disk_usage,
            'database_health': self._check_database_health,
            'log_files': self._check_log_files,
            'process_count': self._check_process_count,
        }
        
        # Performance thresholds
        self.thresholds = {
            'cpu_usage': {'warning': 80.0, 'critical': 95.0},
            'memory_usage': {'warning': 85.0, 'critical': 95.0},
            'disk_usage': {'warning': 85.0, 'critical': 95.0},
            'response_time': {'warning': 2.0, 'critical': 5.0},
            'error_rate': {'warning': 5.0, 'critical': 10.0},
        }
    
    def register_component(self, component_name: str, custom_checks: Dict[str, Callable] = None):
        """Register a component for health monitoring"""
        with self.lock:
            if component_name not in self.component_health:
                self.component_health[component_name] = ComponentHealth(
                    component_name=component_name,
                    status=HealthStatus.UNKNOWN
                )
            
            # Add custom health checks for this component
            if custom_checks:
                for check_name, check_func in custom_checks.items():
                    self.health_checks[f"{component_name}_{check_name}"] = check_func
    
    def update_component_status(self, component_name: str, status: HealthStatus, 
                              message: str = "", error_count: int = 0):
        """Update component health status"""
        with self.lock:
            if component_name not in self.component_health:
                self.register_component(component_name)
            
            component = self.component_health[component_name]
            component.status = status
            component.last_check = datetime.now()
            component.error_count = error_count
            if message:
                component.last_error = message
    
    def add_metric(self, component_name: str, metric_name: str, value: Any, 
                   unit: str = "", threshold_warning: float = None, 
                   threshold_critical: float = None):
        """Add a metric for a component"""
        
        # Determine status based on thresholds
        status = HealthStatus.HEALTHY
        message = ""
        
        if isinstance(value, (int, float)) and threshold_critical is not None:
            if value >= threshold_critical:
                status = HealthStatus.CRITICAL
                message = f"Critical threshold exceeded: {value} >= {threshold_critical}"
            elif threshold_warning is not None and value >= threshold_warning:
                status = HealthStatus.WARNING
                message = f"Warning threshold exceeded: {value} >= {threshold_warning}"
        
        metric = HealthMetric(
            name=metric_name,
            value=value,
            unit=unit,
            status=status,
            threshold_warning=threshold_warning,
            threshold_critical=threshold_critical,
            message=message
        )
        
        with self.lock:
            if component_name not in self.component_health:
                self.register_component(component_name)
            
            self.component_health[component_name].metrics[metric_name] = metric
    
    def start_monitoring(self):
        """Start the health monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop the health monitoring thread"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self._run_all_health_checks()
                self._update_system_metrics()
                self._record_health_snapshot()
                time.sleep(self.check_interval)
            except Exception as e:
                # Log error but continue monitoring
                print(f"Health monitoring error: {e}")
                time.sleep(self.check_interval)
    
    def _run_all_health_checks(self):
        """Run all registered health checks"""
        for check_name, check_func in self.health_checks.items():
            try:
                check_func()
            except Exception as e:
                # Record failed health check
                self.system_metrics[f"{check_name}_error"] = HealthMetric(
                    name=f"{check_name}_error",
                    value=str(e),
                    unit="error",
                    status=HealthStatus.CRITICAL,
                    message=f"Health check {check_name} failed: {e}"
                )
    
    def _check_cpu_usage(self):
        """Check CPU usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        thresholds = self.thresholds.get('cpu_usage', {})
        
        self.system_metrics['cpu_usage'] = HealthMetric(
            name='cpu_usage',
            value=cpu_percent,
            unit='percent',
            status=self._get_status_from_thresholds(cpu_percent, thresholds),
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical')
        )
    
    def _check_memory_usage(self):
        """Check memory usage"""
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        thresholds = self.thresholds.get('memory_usage', {})
        
        self.system_metrics['memory_usage'] = HealthMetric(
            name='memory_usage',
            value=memory_percent,
            unit='percent',
            status=self._get_status_from_thresholds(memory_percent, thresholds),
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical')
        )
        
        # Also track absolute memory values
        self.system_metrics['memory_total'] = HealthMetric(
            name='memory_total',
            value=memory.total // (1024**3),  # GB
            unit='GB',
            status=HealthStatus.HEALTHY
        )
        
        self.system_metrics['memory_available'] = HealthMetric(
            name='memory_available',
            value=memory.available // (1024**3),  # GB
            unit='GB',
            status=HealthStatus.HEALTHY
        )
    
    def _check_disk_usage(self):
        """Check disk usage"""
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        thresholds = self.thresholds.get('disk_usage', {})
        
        self.system_metrics['disk_usage'] = HealthMetric(
            name='disk_usage',
            value=disk_percent,
            unit='percent',
            status=self._get_status_from_thresholds(disk_percent, thresholds),
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical')
        )
        
        self.system_metrics['disk_free'] = HealthMetric(
            name='disk_free',
            value=disk.free // (1024**3),  # GB
            unit='GB',
            status=HealthStatus.HEALTHY
        )
    
    def _check_database_health(self):
        """Check database health"""
        try:
            from core.database_config import DatabaseConfig
            
            if DatabaseConfig.is_postgresql():
                # PostgreSQL health check
                import psycopg2
                params = DatabaseConfig.get_raw_connection_params()
                conn = psycopg2.connect(
                    host=params['host'],
                    port=params['port'],
                    database=params['database'],
                    user=params['user'],
                    password=params['password'],
                    connect_timeout=5
                )
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tweets")
                tweet_count = cursor.fetchone()[0]
                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size_str = cursor.fetchone()[0]
                conn.close()
                
                self.system_metrics['database_connectivity'] = HealthMetric(
                    name='database_connectivity',
                    value='connected',
                    unit='status',
                    status=HealthStatus.HEALTHY,
                    message=f"PostgreSQL accessible with {tweet_count} tweets (Size: {db_size_str})"
                )
                
                self.system_metrics['database_size'] = HealthMetric(
                    name='database_size',
                    value=db_size_str,
                    unit='PostgreSQL',
                    status=HealthStatus.HEALTHY
                )
            else:
                # SQLite health check
                import sqlite3
                from pathlib import Path
                params = DatabaseConfig.get_raw_connection_params()
                db_path = params['database']
                
                if Path(db_path).exists():
                    with sqlite3.connect(db_path, timeout=5) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM tweets")
                        tweet_count = cursor.fetchone()[0]
                    
                    # Check database file size
                    db_size = Path(db_path).stat().st_size // (1024**2)  # MB
                    
                    self.system_metrics['database_connectivity'] = HealthMetric(
                        name='database_connectivity',
                        value='connected',
                        unit='status',
                        status=HealthStatus.HEALTHY,
                        message=f"SQLite accessible with {tweet_count} tweets"
                    )
                    
                    self.system_metrics['database_size'] = HealthMetric(
                        name='database_size',
                        value=db_size,
                        unit='MB',
                        status=HealthStatus.HEALTHY
                    )
                else:
                    self.system_metrics['database_connectivity'] = HealthMetric(
                        name='database_connectivity',
                        value='missing',
                        unit='status',
                        status=HealthStatus.CRITICAL,
                        message="Database file not found"
                    )
        
        except Exception as e:
            self.system_metrics['database_connectivity'] = HealthMetric(
                name='database_connectivity',
                value='error',
                unit='status',
                status=HealthStatus.CRITICAL,
                message=f"Database error: {e}"
            )
    
    def _check_log_files(self):
        """Check log file health"""
        logs_dir = Path('./logs')
        if logs_dir.exists():
            log_files = list(logs_dir.glob('*.log'))
            total_log_size = sum(f.stat().st_size for f in log_files) // (1024**2)  # MB
            
            self.system_metrics['log_files_count'] = HealthMetric(
                name='log_files_count',
                value=len(log_files),
                unit='files',
                status=HealthStatus.HEALTHY
            )
            
            self.system_metrics['log_files_size'] = HealthMetric(
                name='log_files_size',
                value=total_log_size,
                unit='MB',
                status=HealthStatus.WARNING if total_log_size > 100 else HealthStatus.HEALTHY,
                threshold_warning=100,
                threshold_critical=500
            )
        else:
            self.system_metrics['log_files_count'] = HealthMetric(
                name='log_files_count',
                value=0,
                unit='files',
                status=HealthStatus.WARNING,
                message="Logs directory not found"
            )
    
    def _check_process_count(self):
        """Check running process count"""
        process_count = len(list(psutil.process_iter()))
        
        self.system_metrics['process_count'] = HealthMetric(
            name='process_count',
            value=process_count,
            unit='processes',
            status=HealthStatus.HEALTHY,
            message=f"System running {process_count} processes"
        )
    
    def _get_status_from_thresholds(self, value: float, thresholds: Dict[str, float]) -> HealthStatus:
        """Determine health status based on thresholds"""
        critical = thresholds.get('critical')
        warning = thresholds.get('warning')
        
        if critical is not None and value >= critical:
            return HealthStatus.CRITICAL
        elif warning is not None and value >= warning:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def _update_system_metrics(self):
        """Update overall system metrics"""
        with self.lock:
            # Calculate overall system health
            all_statuses = [metric.status for metric in self.system_metrics.values()]
            all_statuses.extend([comp.status for comp in self.component_health.values()])
            
            if HealthStatus.CRITICAL in all_statuses:
                overall_status = HealthStatus.CRITICAL
            elif HealthStatus.DEGRADED in all_statuses:
                overall_status = HealthStatus.DEGRADED
            elif HealthStatus.WARNING in all_statuses:
                overall_status = HealthStatus.WARNING
            else:
                overall_status = HealthStatus.HEALTHY
            
            self.system_metrics['overall_health'] = HealthMetric(
                name='overall_health',
                value=overall_status.value,
                unit='status',
                status=overall_status,
                message=f"System health: {overall_status.value}"
            )
    
    def _record_health_snapshot(self):
        """Record a snapshot of current health status"""
        with self.lock:
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': self.system_metrics.get('overall_health', HealthMetric('', '', '', HealthStatus.UNKNOWN)).status.value,
                'system_metrics': {
                    name: {
                        'value': metric.value,
                        'unit': metric.unit,
                        'status': metric.status.value
                    }
                    for name, metric in self.system_metrics.items()
                },
                'component_health': {
                    name: {
                        'status': component.status.value,
                        'error_count': component.error_count,
                        'uptime_seconds': (datetime.now() - component.last_check).total_seconds()
                    }
                    for name, component in self.component_health.items()
                }
            }
            
            # Keep only last 100 snapshots
            self.health_history.append(snapshot)
            if len(self.health_history) > 100:
                self.health_history.pop(0)
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        with self.lock:
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_health': self.system_metrics.get('overall_health', HealthMetric('', '', '', HealthStatus.UNKNOWN)).status.value,
                'system_metrics': {
                    name: {
                        'value': metric.value,
                        'unit': metric.unit,
                        'status': metric.status.value,
                        'message': metric.message,
                        'threshold_warning': metric.threshold_warning,
                        'threshold_critical': metric.threshold_critical,
                        'timestamp': metric.timestamp.isoformat()
                    }
                    for name, metric in self.system_metrics.items()
                },
                'component_health': {
                    name: {
                        'status': component.status.value,
                        'last_check': component.last_check.isoformat(),
                        'error_count': component.error_count,
                        'last_error': component.last_error,
                        'metrics': {
                            metric_name: {
                                'value': metric.value,
                                'unit': metric.unit,
                                'status': metric.status.value,
                                'message': metric.message
                            }
                            for metric_name, metric in component.metrics.items()
                        }
                    }
                    for name, component in self.component_health.items()
                },
                'monitoring_status': {
                    'running': self.running,
                    'check_interval': self.check_interval,
                    'history_length': len(self.health_history)
                }
            }
    
    def get_health_history(self, limit: int = 24) -> List[Dict[str, Any]]:
        """Get recent health history"""
        with self.lock:
            return self.health_history[-limit:] if self.health_history else []
    
    def is_healthy(self) -> bool:
        """Check if system is overall healthy"""
        overall_metric = self.system_metrics.get('overall_health')
        if overall_metric:
            return overall_metric.status in [HealthStatus.HEALTHY, HealthStatus.WARNING]
        return False


# Global health monitor instance
global_health_monitor = HealthMonitor()


def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor instance"""
    return global_health_monitor


def start_health_monitoring():
    """Start global health monitoring"""
    global_health_monitor.start_monitoring()


def stop_health_monitoring():
    """Stop global health monitoring"""
    global_health_monitor.stop_monitoring()


def get_system_health_report() -> Dict[str, Any]:
    """Get comprehensive system health report"""
    return global_health_monitor.get_health_report()
