"""Flink REST API client để giám sát job và quản lý cluster."""
import requests
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FlinkConfig:
    """Cấu hình kết nối Flink."""
    jobmanager_url: str = "http://localhost:8092"  # Flink Web UI


@dataclass
class FlinkJob:
    """Đại diện cho một Flink job."""
    job_id: str
    name: str
    state: str  # CREATED, RUNNING, FAILING, FAILED, CANCELLING, CANCELED, FINISHED, etc.
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: int
    
    @classmethod
    def from_json(cls, data: dict) -> "FlinkJob":
        """Tạo FlinkJob từ phản hồi JSON."""
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
    """Đại diện cho một Flink TaskManager."""
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
    """Client để việc giám sát cluster Flink và quản lý job."""
    
    def __init__(self, config: Optional[FlinkConfig] = None):
        """
        Khởi tạo Flink client.
        
        Args:
            config: Cấu hình kết nối Flink
        """
        self.config = config or FlinkConfig()
        self._connected = False
        self._check_connection()
    
    def _check_connection(self) -> None:
        """Kiểm tra xem Flink JobManager có thể truy cập được không."""
        # Kiểm tra kết nối bằng cách gọi overview endpoint
        resp = requests.get(f"{self.config.jobmanager_url}/overview", timeout=5)
        self._connected = resp.status_code == 200
        if self._connected:
            logger.info(f"Flink connected: {self.config.jobmanager_url}")
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra xem Flink đã kết nối chưa."""
        return self._connected
    
    def refresh_connection(self) -> bool:
        """Làm mới trạng thái kết nối."""
        self._check_connection()
        return self._connected
    
    def get_cluster_overview(self) -> Dict[str, Any]:
        """
        Lấy tổng quan về Flink cluster.
        
        Returns:
            Dict chứa các số liệu cluster
        """
        if not self._connected:
            return {}
        
        # Lấy số liệu tổng quan
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
    
    def get_cluster_config(self) -> Dict[str, str]:
        """Lấy cấu hình Flink cluster."""
        if not self._connected:
            return {}
        
        # Lấy cấu hình Flink
        resp = requests.get(f"{self.config.jobmanager_url}/config", timeout=5)
        configs = {}
        for item in resp.json():
            configs[item.get("key", "")] = item.get("value", "")
        return configs
    
    def get_jobs(self, status: str = "all") -> List[FlinkJob]:
        """
        Lấy danh sách các Flink jobs.
        
        Args:
            status: Lọc theo trạng thái - "running", "completed", hoặc "all"
            
        Returns:
            Danh sách các đối tượng FlinkJob
        """
        if not self._connected:
            return []
        
        # Lấy danh sách jobs
        resp = requests.get(f"{self.config.jobmanager_url}/jobs", timeout=5)
        data = resp.json()
        
        jobs = []
        for job_info in data.get("jobs", []):
            job_id = job_info.get("id", "")
            
            # Lấy chi tiết job
            detail_resp = requests.get(
                f"{self.config.jobmanager_url}/jobs/{job_id}",
                timeout=5
            )
            
            if detail_resp.status_code == 200:
                job_detail = detail_resp.json()
                job = FlinkJob.from_json(job_detail)
                
                # Lọc theo trạng thái
                if status == "running" and job.state != "RUNNING":
                    continue
                elif status == "completed" and job.state not in ("FINISHED", "CANCELED", "FAILED"):
                    continue
                
                jobs.append(job)
        
        return jobs
    
    def get_job_detail(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết về một job cụ thể."""
        if not self._connected:
            return None
        
        # Lấy thông tin chi tiết job
        resp = requests.get(
            f"{self.config.jobmanager_url}/jobs/{job_id}",
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    
    def get_job_exceptions(self, job_id: str) -> List[Dict[str, Any]]:
        """Lấy các ngoại lệ (errors) cho một job cụ thể."""
        if not self._connected:
            return []
        
        # Lấy job exceptions
        resp = requests.get(
            f"{self.config.jobmanager_url}/jobs/{job_id}/exceptions",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("all-exceptions", [])
        return []
    
    def get_taskmanagers(self) -> List[FlinkTaskManager]:
        """Lấy danh sách các TaskManagers."""
        if not self._connected:
            return []
        
        # Lấy danh sách task managers
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
    
    def get_taskmanager_detail(self, tm_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết về một TaskManager cụ thể."""
        if not self._connected:
            return None
        
        # Lấy thông tin chi tiết taskmanager
        resp = requests.get(
            f"{self.config.jobmanager_url}/taskmanagers/{tm_id}",
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Hủy một job đang chạy."""
        if not self._connected:
            return False
        
        # Hủy job qua REST API
        resp = requests.patch(
            f"{self.config.jobmanager_url}/jobs/{job_id}",
            timeout=10
        )
        return resp.status_code in (200, 202)
