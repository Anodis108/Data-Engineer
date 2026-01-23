"""Spark REST API client for job monitoring and cluster management."""
import requests
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SparkConfig:
    """Spark connection configuration."""
    master_url: str = "http://localhost:8090"  # Spark Master Web UI
    submit_url: str = "spark://localhost:7077"  # Spark Master RPC


@dataclass
class SparkApplication:
    """Represents a Spark application."""
    app_id: str
    name: str
    state: str  # "RUNNING", "FINISHED", "FAILED", "WAITING"
    start_time: datetime
    duration_ms: int
    cores: int
    memory_per_executor: str
    
    @classmethod
    def from_json(cls, data: dict) -> "SparkApplication":
        """Create SparkApplication from JSON response."""
        attempts = data.get("attempts", [{}])
        latest_attempt = attempts[0] if attempts else {}
        
        start_time_str = latest_attempt.get("startTime", "")
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except:
            start_time = datetime.now()
        
        # Determine state
        if latest_attempt.get("completed", False):
            state = "FINISHED"
        else:
            state = "RUNNING"
        
        return cls(
            app_id=data.get("id", "unknown"),
            name=data.get("name", "Unknown Application"),
            state=state,
            start_time=start_time,
            duration_ms=latest_attempt.get("duration", 0),
            cores=data.get("coresGranted", 0),
            memory_per_executor=data.get("memoryPerExecutorMB", "0")
        )


@dataclass
class SparkWorker:
    """Represents a Spark worker node."""
    worker_id: str
    host: str
    port: int
    cores: int
    cores_used: int
    memory: int
    memory_used: int
    state: str


class SparkClient:
    """Client for Spark cluster monitoring and job submission."""
    
    def __init__(self, config: Optional[SparkConfig] = None):
        """
        Initialize Spark client.
        
        Args:
            config: Spark connection configuration
        """
        self.config = config or SparkConfig()
        self._connected = False
        self._check_connection()
    
    def _check_connection(self) -> None:
        """Check if Spark Master is reachable."""
        try:
            resp = requests.get(f"{self.config.master_url}/json/", timeout=5)
            self._connected = resp.status_code == 200
            if self._connected:
                logger.info(f"Spark connected: {self.config.master_url}")
        except requests.RequestException as e:
            logger.warning(f"Spark connection failed: {e}")
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if Spark is connected."""
        return self._connected
    
    def refresh_connection(self) -> bool:
        """Refresh connection status."""
        self._check_connection()
        return self._connected
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """
        Get Spark cluster information.
        
        Returns:
            Dict with cluster status, workers, apps, etc.
        """
        if not self._connected:
            return {}
        
        try:
            resp = requests.get(f"{self.config.master_url}/json/", timeout=5)
            data = resp.json()
            
            return {
                "status": data.get("status", "UNKNOWN"),
                "url": data.get("url", ""),
                "workers_alive": data.get("aliveworkers", 0),
                "cores_total": data.get("cores", 0),
                "cores_used": data.get("coresinuse", 0),
                "memory_total_mb": data.get("memory", 0),
                "memory_used_mb": data.get("memoryused", 0),
                "active_apps": len(data.get("activeapps", [])),
                "completed_apps": len(data.get("completedapps", []))
            }
        except Exception as e:
            logger.error(f"Failed to get cluster info: {e}")
            return {}
    
    def get_applications(self, status: str = "all") -> List[SparkApplication]:
        """
        Get list of Spark applications.
        
        Args:
            status: Filter by status - "running", "completed", or "all"
            
        Returns:
            List of SparkApplication objects
        """
        if not self._connected:
            return []
        
        try:
            # Use REST API
            if status == "running":
                endpoint = f"{self.config.master_url}/api/v1/applications?status=running"
            elif status == "completed":
                endpoint = f"{self.config.master_url}/api/v1/applications?status=completed"
            else:
                endpoint = f"{self.config.master_url}/api/v1/applications"
            
            resp = requests.get(endpoint, timeout=5)
            
            if resp.status_code != 200:
                # Fallback to master JSON
                return self._get_apps_from_master_json(status)
            
            apps = []
            for app_data in resp.json():
                apps.append(SparkApplication.from_json(app_data))
            
            return apps
            
        except Exception as e:
            logger.error(f"Failed to get applications: {e}")
            return []
    
    def _get_apps_from_master_json(self, status: str) -> List[SparkApplication]:
        """Fallback method to get apps from master JSON endpoint."""
        try:
            resp = requests.get(f"{self.config.master_url}/json/", timeout=5)
            data = resp.json()
            
            apps = []
            
            if status in ("running", "all"):
                for app in data.get("activeapps", []):
                    apps.append(SparkApplication(
                        app_id=app.get("id", ""),
                        name=app.get("name", ""),
                        state="RUNNING",
                        start_time=datetime.now(),
                        duration_ms=app.get("duration", 0),
                        cores=app.get("cores", 0),
                        memory_per_executor=str(app.get("memoryperslave", 0))
                    ))
            
            if status in ("completed", "all"):
                for app in data.get("completedapps", []):
                    apps.append(SparkApplication(
                        app_id=app.get("id", ""),
                        name=app.get("name", ""),
                        state="FINISHED",
                        start_time=datetime.now(),
                        duration_ms=app.get("duration", 0),
                        cores=app.get("cores", 0),
                        memory_per_executor=str(app.get("memoryperslave", 0))
                    ))
            
            return apps
        except Exception as e:
            logger.error(f"Failed to get apps from master: {e}")
            return []
    
    def get_workers(self) -> List[SparkWorker]:
        """Get list of Spark workers."""
        if not self._connected:
            return []
        
        try:
            resp = requests.get(f"{self.config.master_url}/json/", timeout=5)
            data = resp.json()
            
            workers = []
            for w in data.get("workers", []):
                workers.append(SparkWorker(
                    worker_id=w.get("id", ""),
                    host=w.get("host", ""),
                    port=w.get("port", 0),
                    cores=w.get("cores", 0),
                    cores_used=w.get("coresused", 0),
                    memory=w.get("memory", 0),
                    memory_used=w.get("memoryused", 0),
                    state=w.get("state", "UNKNOWN")
                ))
            
            return workers
        except Exception as e:
            logger.error(f"Failed to get workers: {e}")
            return []
    
    def get_application_detail(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific application."""
        if not self._connected:
            return None
        
        try:
            resp = requests.get(
                f"{self.config.master_url}/api/v1/applications/{app_id}",
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get app detail: {e}")
            return None
    
    def get_application_jobs(self, app_id: str) -> List[Dict[str, Any]]:
        """Get jobs for a specific application."""
        if not self._connected:
            return []
        
        try:
            resp = requests.get(
                f"{self.config.master_url}/api/v1/applications/{app_id}/jobs",
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Failed to get app jobs: {e}")
            return []
