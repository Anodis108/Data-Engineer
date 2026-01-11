"""Trino client for querying data lake via SQL."""
import logging
from typing import Optional, Any
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TrinoConfig:
    """Trino connection configuration."""
    host: str = "localhost"
    port: int = 8080
    user: str = "trino"
    catalog: str = "hive"
    schema: str = "raw"


class TrinoClient:
    """Client for executing SQL queries against Trino."""
    
    def __init__(self, config: Optional[TrinoConfig] = None):
        """
        Initialize Trino client.
        
        Args:
            config: Trino connection configuration
        """
        self.config = config or TrinoConfig()
        self._connected = False
        self._connection = None
        
        try:
            from trino.dbapi import connect
            from trino.auth import BasicAuthentication
            
            self._connection = connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                catalog=self.config.catalog,
                schema=self.config.schema,
            )
            
            # Test connection
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            self._connected = True
            logger.info(f"Trino connected: {self.config.host}:{self.config.port}")
            
        except ImportError:
            logger.error("Trino package not installed. Run: pip install trino")
        except Exception as e:
            logger.error(f"Trino connection failed: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if Trino is connected."""
        return self._connected and self._connection is not None
    
    def execute_query(self, query: str) -> Optional[pd.DataFrame]:
        """
        Execute SQL query and return results as DataFrame.
        
        Args:
            query: SQL query to execute
            
        Returns:
            DataFrame with results, or None if failed
        """
        if not self.is_connected:
            logger.warning("Trino not connected")
            return None
        
        try:
            cursor = self._connection.cursor()
            cursor.execute(query)
            
            # Fetch results
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            cursor.close()
            
            if rows:
                return pd.DataFrame(rows, columns=columns)
            return pd.DataFrame(columns=columns)
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return None
    
    def get_schemas(self) -> list[str]:
        """Get list of available schemas."""
        df = self.execute_query("SHOW SCHEMAS")
        if df is not None and not df.empty:
            return df.iloc[:, 0].tolist()
        return []
    
    def get_tables(self, schema: str = "raw") -> list[str]:
        """Get list of tables in a schema."""
        df = self.execute_query(f"SHOW TABLES FROM {schema}")
        if df is not None and not df.empty:
            return df.iloc[:, 0].tolist()
        return []
    
    def get_table_preview(self, table: str, schema: str = "raw", limit: int = 100) -> Optional[pd.DataFrame]:
        """Get preview of table data."""
        return self.execute_query(f"SELECT * FROM {schema}.{table} LIMIT {limit}")
    
    def get_event_statistics(self) -> Optional[pd.DataFrame]:
        """Get aggregated event statistics."""
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
        """Get event count by hour for charting."""
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
        """Get most recent events."""
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
        """Close Trino connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Trino connection closed")
            except Exception as e:
                logger.warning(f"Error closing Trino: {e}")
        self._connected = False
