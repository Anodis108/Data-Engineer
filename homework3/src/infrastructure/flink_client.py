"""Flink REST API client for job monitoring and cluster management."""
import requests
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FlinkConfig:
    """Flink connection configuration."""
    jobmanager_url: str = "http://localhost:8092"  # Flink Web UI


@dataclass
class FlinkJob:
    """Represents a Flink job."""
    job_id: str
    name: str
    state: str  # CREATED, RUNNING, FAILING, FAILED, CANCELLING, CANCELED, FINISHED, etc.
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: int
    
    @classmethod
    def from_json(cls, data: dict) -> "FlinkJob":
        """Create FlinkJob from JSON response."""
        start_time = datetime.fromtimestamp(data.get("start-time", 0) / 1000)
        end_time_ms = data.get("end-time", -1)
        end_time = datetime.fromtimestamp(end_time_ms / 1000) if end_time_ms > 0 else None
        
        return cls(
            job_id=data.get("jid", data.get("id", "unknown")),
            name=data.get("name", "Unknown Job"),
            state=data.get("state", "UNKNOWN"),
            start_time=start_time,
            end_time=end_time,
            duration_ms=data.get("duration", 0)
        )


@dataclass
class FlinkTaskManager:
    """Represents a Flink TaskManager."""
    tm_id: str
    path: str
    data_port: int
    time_since_heartbeat: int
    slots_number: int
    free_slots: int
    total_resource_cpu: float
    total_resource_memory: int
    hardware_cpu_cores: int
    hardware_physical_memory: int


class FlinkClient:
    """Client for Flink cluster monitoring and job management."""
    
    def __init__(self, config: Optional[FlinkConfig] = None):
        """
        Initialize Flink client.
        
        Args:
            config: Flink connection configuration
        """
        self.config = config or FlinkConfig()
        self._connected = False
        self._check_connection()
    
    def _check_connection(self) -> None:
        """Check if Flink JobManager is reachable."""
        try:
            resp = requests.get(f"{self.config.jobmanager_url}/overview", timeout=5)
            self._connected = resp.status_code == 200
            if self._connected:
                logger.info(f"Flink connected: {self.config.jobmanager_url}")
        except requests.RequestException as e:
            logger.warning(f"Flink connection failed: {e}")
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if Flink is connected."""
        return self._connected
    
    def refresh_connection(self) -> bool:
        """Refresh connection status."""
        self._check_connection()
        return self._connected
    
    def get_cluster_overview(self) -> Dict[str, Any]:
        """
        Get Flink cluster overview.
        
        Returns:
            Dict with cluster metrics
        """
        if not self._connected:
            return {}
        
        try:
            resp = requests.get(f"{self.config.jobmanager_url}/overview", timeout=5)
            data = resp.json()
            
            return {
                "flink_version": data.get("flink-version", "unknown"),
                "taskmanagers": data.get("taskmanagers", 0),
                "slots_total": data.get("slots-total", 0),
                "slots_available": data.get("slots-available", 0),
                "jobs_running": data.get("jobs-running", 0),
                "jobs_finished": data.get("jobs-finished", 0),
                "jobs_cancelled": data.get("jobs-cancelled", 0),
                "jobs_failed": data.get("jobs-failed", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get cluster overview: {e}")
            return {}
    
    def get_cluster_config(self) -> Dict[str, str]:
        """Get Flink cluster configuration."""
        if not self._connected:
            return {}
        
        try:
            resp = requests.get(f"{self.config.jobmanager_url}/config", timeout=5)
            configs = {}
            for item in resp.json():
                configs[item.get("key", "")] = item.get("value", "")
            return configs
        except Exception as e:
            logger.error(f"Failed to get cluster config: {e}")
            return {}
    
    def get_jobs(self, status: str = "all") -> List[FlinkJob]:
        """
        Get list of Flink jobs.
        
        Args:
            status: Filter by status - "running", "completed", or "all"
            
        Returns:
            List of FlinkJob objects
        """
        if not self._connected:
            return []
        
        try:
            resp = requests.get(f"{self.config.jobmanager_url}/jobs", timeout=5)
            data = resp.json()
            
            jobs = []
            for job_info in data.get("jobs", []):
                job_id = job_info.get("id", "")
                
                # Get job details
                detail_resp = requests.get(
                    f"{self.config.jobmanager_url}/jobs/{job_id}",
                    timeout=5
                )
                
                if detail_resp.status_code == 200:
                    job_detail = detail_resp.json()
                    job = FlinkJob.from_json(job_detail)
                    
                    # Filter by status
                    if status == "running" and job.state != "RUNNING":
                        continue
                    elif status == "completed" and job.state not in ("FINISHED", "CANCELED", "FAILED"):
                        continue
                    
                    jobs.append(job)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to get jobs: {e}")
            return []
    
    def get_job_detail(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific job."""
        if not self._connected:
            return None
        
        try:
            resp = requests.get(
                f"{self.config.jobmanager_url}/jobs/{job_id}",
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get job detail: {e}")
            return None
    
    def get_job_exceptions(self, job_id: str) -> List[Dict[str, Any]]:
        """Get exceptions for a specific job."""
        if not self._connected:
            return []
        
        try:
            resp = requests.get(
                f"{self.config.jobmanager_url}/jobs/{job_id}/exceptions",
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("all-exceptions", [])
            return []
        except Exception as e:
            logger.error(f"Failed to get job exceptions: {e}")
            return []
    
    def get_taskmanagers(self) -> List[FlinkTaskManager]:
        """Get list of TaskManagers."""
        if not self._connected:
            return []
        
        try:
            resp = requests.get(f"{self.config.jobmanager_url}/taskmanagers", timeout=5)
            data = resp.json()
            
            tms = []
            for tm in data.get("taskmanagers", []):
                hardware = tm.get("hardware", {})
                tms.append(FlinkTaskManager(
                    tm_id=tm.get("id", ""),
                    path=tm.get("path", ""),
                    data_port=tm.get("dataPort", 0),
                    time_since_heartbeat=tm.get("timeSinceLastHeartbeat", 0),
                    slots_number=tm.get("slotsNumber", 0),
                    free_slots=tm.get("freeSlots", 0),
                    total_resource_cpu=tm.get("totalResource", {}).get("cpuCores", 0),
                    total_resource_memory=tm.get("totalResource", {}).get("taskHeapMemory", 0),
                    hardware_cpu_cores=hardware.get("cpuCores", 0),
                    hardware_physical_memory=hardware.get("physicalMemory", 0)
                ))
            
            return tms
        except Exception as e:
            logger.error(f"Failed to get taskmanagers: {e}")
            return []
    
    def get_taskmanager_detail(self, tm_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific TaskManager."""
        if not self._connected:
            return None
        
        try:
            resp = requests.get(
                f"{self.config.jobmanager_url}/taskmanagers/{tm_id}",
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get taskmanager detail: {e}")
            return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if not self._connected:
            return False
        
        try:
            resp = requests.patch(
                f"{self.config.jobmanager_url}/jobs/{job_id}",
                timeout=10
            )
            return resp.status_code in (200, 202)
        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return False
