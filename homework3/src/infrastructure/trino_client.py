"""Trino client để truy vấn data lake qua SQL."""
import logging
from typing import Optional, Any
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TrinoConfig:
    """Cấu hình kết nối Trino."""
    host: str = "localhost"
    port: int = 8080
    user: str = "trino"
    catalog: str = "hive"
    schema: str = "raw"


class TrinoClient:
    """Client để thực thi các truy vấn SQL trên Trino."""
    
    def __init__(self, config: Optional[TrinoConfig] = None):
        """
        Khởi tạo Trino client.
        
        Args:
            config: Cấu hình kết nối Trino
        """
        self.config = config or TrinoConfig()
        self._connected = False
        self._connection = None
        
        # Kết nối tới Trino (Hive catalog)
        from trino.dbapi import connect
        from trino.auth import BasicAuthentication
        
        self._connection = connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            catalog=self.config.catalog,
            schema=self.config.schema,
        )
        
        # Kiểm tra kết nối bằng cách chạy một truy vấn đơn giản
        cursor = self._connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        
        self._connected = True
        logger.info(f"Trino connected: {self.config.host}:{self.config.port}")
        
        # Khởi tạo schema và tables
        self._init_schema()
            
    def _init_schema(self) -> None:
        """Khởi tạo schema và các bảng nếu chúng chưa tồn tại."""
        if not self.is_connected:
            return

        # Tạo schema trong MinIO/S3 nếu chưa tồn tại
        self.execute_query(f"CREATE SCHEMA IF NOT EXISTS {self.config.schema} WITH (location = 's3://lake/{self.config.schema}/')")
        
        # Tạo bảng external cho các sự kiện thị giác (định dạng Parquet)
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.config.schema}.vision_events (
            event_id VARCHAR,
            ts_start TIMESTAMP,
            ts_end TIMESTAMP,
            person_count INTEGER,
            conf_avg DOUBLE,
            conf_max DOUBLE,
            frame_uri VARCHAR,
            event_type VARCHAR,
            camera_id VARCHAR,
            date VARCHAR,
            hour VARCHAR
        )
        WITH (
            format = 'PARQUET',
            external_location = 's3://lake/raw/events/person_detection/',
            partitioned_by = ARRAY['camera_id', 'date', 'hour']
        )
        """
        self.execute_query(create_table_sql)
        
        # Đồng bộ metadata phân vùng để khám phá các file mới
        self.execute_query(f"CALL system.sync_partition_metadata('{self.config.schema}', 'vision_events', 'ADD')")
            
        logger.info("Trino schema and table initialized")
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra xem Trino đã kết nối chưa."""
        return self._connected and self._connection is not None
    
    def execute_query(self, query: str) -> Optional[pd.DataFrame]:
        """
        Thực thi truy vấn SQL và trả về kết quả dưới dạng DataFrame.
        
        Args:
            query: Truy vấn SQL cần thực thi
            
        Returns:
            DataFrame chứa kết quả, hoặc None nếu thất bại
        """
        if not self.is_connected:
            logger.warning("Trino not connected")
            return None
        
        # Thực thi truy vấn và lấy tất cả kết quả
        cursor = self._connection.cursor()
        cursor.execute(query)
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        cursor.close()
        
        if rows:
            return pd.DataFrame(rows, columns=columns)
        return pd.DataFrame(columns=columns)
    
    def get_schemas(self) -> list[str]:
        """Lấy danh sách các schemas có sẵn."""
        df = self.execute_query("SHOW SCHEMAS")
        if df is not None and not df.empty:
            return df.iloc[:, 0].tolist()
        return []
    
    def get_tables(self, schema: str = "raw") -> list[str]:
        """Lấy danh sách các bảng trong một schema."""
        df = self.execute_query(f"SHOW TABLES FROM {schema}")
        if df is not None and not df.empty:
            return df.iloc[:, 0].tolist()
        return []
    
    def get_table_preview(self, table: str, schema: str = "raw", limit: int = 100) -> Optional[pd.DataFrame]:
        """Lấy xem trước dữ liệu của bảng."""
        return self.execute_query(f"SELECT * FROM {schema}.{table} LIMIT {limit}")
    
    def get_event_statistics(self) -> Optional[pd.DataFrame]:
        """Lấy thống kê sự kiện đã được tổng hợp."""
        query = """
        SELECT 
            camera_id,
            event_type,
            COUNT(*) as event_count,
            AVG(person_count) as avg_person_count,
            AVG(conf_avg) as avg_confidence,
            MAX(conf_max) as max_confidence,
            MIN(ts_start) as first_event,
            MAX(ts_end) as last_event
        FROM raw.vision_events
        GROUP BY camera_id, event_type
        ORDER BY event_count DESC
        """
        return self.execute_query(query)
    
    def get_events_by_hour(self, camera_id: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Lấy số lượng sự kiện theo giờ để vẽ biểu đồ."""
        where_clause = f"WHERE camera_id = '{camera_id}'" if camera_id else ""
        query = f"""
        SELECT 
            date_trunc('hour', ts_start) as hour,
            event_type,
            COUNT(*) as event_count
        FROM raw.vision_events
        {where_clause}
        GROUP BY date_trunc('hour', ts_start), event_type
        ORDER BY hour DESC
        LIMIT 168
        """
        return self.execute_query(query)
    
    def get_recent_events(self, limit: int = 50) -> Optional[pd.DataFrame]:
        """Lấy các sự kiện gần đây nhất."""
        query = f"""
        SELECT 
            event_id,
            camera_id,
            ts_start,
            ts_end,
            event_type,
            person_count,
            conf_avg,
            conf_max,
            frame_uri
        FROM raw.vision_events
        ORDER BY ts_end DESC
        LIMIT {limit}
        """
        return self.execute_query(query)
    
    def close(self) -> None:
        """Đóng kết nối Trino."""
        if self._connection:
            # Đóng kết nối để giải phóng tài nguyên
            self._connection.close()
            logger.info("Trino connection closed")
        self._connected = False
