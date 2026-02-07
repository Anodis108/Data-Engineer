"""Spark REST API client để giám sát job và quản lý cluster."""
import requests
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SparkConfig:
    """Cấu hình kết nối Spark."""
    master_url: str = "http://localhost:8090"  # Spark Master Web UI
    submit_url: str = "spark://localhost:7077"  # Spark Master RPC


@dataclass
class SparkApplication:
    """Đại diện cho một ứng dụng Spark."""
    app_id: str
    name: str
    state: str  # "RUNNING", "FINISHED", "FAILED", "WAITING"
    start_time: datetime
    duration_ms: int
    cores: int
    memory_per_executor: str
    
    @classmethod
    def from_json(cls, data: dict) -> "SparkApplication":
        """Tạo SparkApplication từ phản hồi JSON."""
        attempts = data.get("attempts", [{}])
        latest_attempt = attempts[0] if attempts else {}
        
        start_time_str = latest_attempt.get("startTime", "")
        # Phân tích thời gian bắt đầu
        start_time_str = latest_attempt.get("startTime", "")
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        
        # Xác định trạng thái
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
    """Đại diện cho một Spark worker node."""
    worker_id: str
    host: str
    port: int
    cores: int
    cores_used: int
    memory: int
    memory_used: int
    state: str


class SparkClient:
    """Client để giám sát Spark cluster và submit job."""
    
    def __init__(self, config: Optional[SparkConfig] = None):
        """
        Khởi tạo Spark client.
        
        Args:
            config: Cấu hình kết nối Spark
        """
        self.config = config or SparkConfig()
        self._connected = False
        self._check_connection()
    
    def _check_connection(self) -> None:
        """Kiểm tra xem Spark Master có thể truy cập được không."""
        # Kiểm tra kết nối bằng cách gọi master JSON endpoint
        resp = requests.get(f"{self.config.master_url}/json/", timeout=5)
        self._connected = resp.status_code == 200
        if self._connected:
            logger.info(f"Spark connected: {self.config.master_url}")
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra xem Spark đã kết nối chưa."""
        return self._connected
    
    def refresh_connection(self) -> bool:
        """Làm mới trạng thái kết nối."""
        self._check_connection()
        return self._connected
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """
        Lấy thông tin về Spark cluster.
        
        Returns:
            Dict chứa trạng thái cluster, workers, apps, v.v.
        """
        if not self._connected:
            return {}
        
        # Lấy thông tin cluster từ master
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
    
    def get_applications(self, status: str = "all") -> List[SparkApplication]:
        """
        Lấy danh sách các ứng dụng Spark.
        
        Args:
            status: Lọc theo trạng thái - "running", "completed", hoặc "all"
            
        Returns:
            Danh sách các đối tượng SparkApplication
        """
        if not self._connected:
            return []
        
        # Lấy danh sách applications qua REST API
        if status == "running":
            endpoint = f"{self.config.master_url}/api/v1/applications?status=running"
        elif status == "completed":
            endpoint = f"{self.config.master_url}/api/v1/applications?status=completed"
        else:
            endpoint = f"{self.config.master_url}/api/v1/applications"
        
        resp = requests.get(endpoint, timeout=5)
        
        if resp.status_code != 200:
            # Fallback sang master JSON
            return self._get_apps_from_master_json(status)
        
        apps = []
        for app_data in resp.json():
            apps.append(SparkApplication.from_json(app_data))
        
        return apps
    
    def _get_apps_from_master_json(self, status: str) -> List[SparkApplication]:
        """Phương thức dự phòng để lấy apps từ master JSON endpoint."""
        # Fallback: Scrape apps từ Master JSON
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
    
    def get_workers(self) -> List[SparkWorker]:
        """Lấy danh sách các Spark workers."""
        if not self._connected:
            return []
        
        # Lấy danh sách workers
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
    
    def get_application_detail(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết về một ứng dụng cụ thể."""
        if not self._connected:
            return None
        
        # Lấy chi tiết app
        resp = requests.get(
            f"{self.config.master_url}/api/v1/applications/{app_id}",
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    
    def get_application_jobs(self, app_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách jobs của một ứng dụng cụ thể."""
        if not self._connected:
            return []
        
        # Lấy jobs của app
        resp = requests.get(
            f"{self.config.master_url}/api/v1/applications/{app_id}/jobs",
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
        return []
