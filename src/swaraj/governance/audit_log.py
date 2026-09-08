"""
SWARAJ Audit Log - SQLite-based append-only audit logging.

SECURITY BOUNDARY:
- Audit entries are append-only from application perspective
- No UPDATE or DELETE operations exposed for audit records
- Security-sensitive entries are hash-chained for tamper detection
- Private keys, secrets, credentials are NEVER logged
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager
from enum import Enum


class AuditEntryType(str, Enum):
    """Types of audit log entries."""
    RUN_START = "run_start"
    RUN_END = "run_end"
    AGENT_STEP = "agent_step"
    ROUTER_DECISION = "router_decision"
    TOOL_INVOCATION = "tool_invocation"
    AUTHORIZATION_RESULT = "authorization_result"
    OUTPUT_ARTIFACT = "output_artifact"
    SELF_CHECK_RESULT = "self_check_result"
    EGRESS_EVENT = "egress_event"
    CERTIFICATE_STATE = "certificate_state"
    SECURITY_EVENT = "security_event"
    RBAC_DECISION = "rbac_decision"


class AuditLog:
    """
    Append-only SQLite audit log with hash-chain for tamper detection.
    
    SECURITY BOUNDARY: Only INSERT operations are exposed.
    UPDATE and DELETE are not available through this interface.
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._last_hash: Optional[str] = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_hash TEXT NOT NULL UNIQUE,
                    previous_hash TEXT,
                    timestamp TEXT NOT NULL,
                    run_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    entry_type TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    is_security_sensitive INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_id ON audit_entries(run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_entries(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entry_type ON audit_entries(entry_type)
            """)
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _compute_entry_hash(
        self,
        timestamp: str,
        entry_type: str,
        event_data: dict,
        previous_hash: Optional[str],
    ) -> str:
        """
        Compute hash for an audit entry.
        
        Hash chain: SHA256(previous_hash + current_entry_data)
        
        SECURITY: Uses deterministic JSON serialization for reproducibility.
        """
        # Create deterministic representation of entry data
        entry_content = {
            "timestamp": timestamp,
            "entry_type": entry_type,
            "event_data": event_data,
        }
        
        # Sort keys for deterministic serialization
        content_json = json.dumps(entry_content, sort_keys=True, separators=(',', ':'))
        
        # Chain with previous hash
        if previous_hash:
            chain_input = previous_hash + content_json
        else:
            chain_input = content_json
        
        return hashlib.sha256(chain_input.encode('utf-8')).hexdigest()
    
    def append(
        self,
        entry_type: AuditEntryType,
        event_data: dict[str, Any],
        run_id: Optional[str] = None,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        is_security_sensitive: bool = False,
    ) -> str:
        """
        Append an audit entry.
        
        SECURITY BOUNDARY:
        - Only INSERT allowed, no UPDATE/DELETE
        - Sensitive data (keys, secrets) must be filtered before calling
        - Returns entry hash for verification
        
        Args:
            entry_type: Type of audit event
            event_data: Event payload (must be JSON-serializable)
            run_id: Associated run ID
            user_id: User who triggered the event
            role: User's role at time of event
            is_security_sensitive: Whether to include in hash chain
        
        Returns:
            Entry hash
        """
        # Filter out sensitive fields from event_data
        filtered_data = self._filter_sensitive_fields(event_data)
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Get previous hash for chaining
        previous_hash = self._get_last_hash() if is_security_sensitive else None
        
        # Compute entry hash
        entry_hash = self._compute_entry_hash(
            timestamp,
            entry_type.value,
            filtered_data,
            previous_hash,
        )
        
        # Insert into database
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_entries 
                (entry_hash, previous_hash, timestamp, run_id, user_id, role, entry_type, event_data, is_security_sensitive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_hash,
                    previous_hash,
                    timestamp,
                    run_id,
                    user_id,
                    role,
                    entry_type.value,
                    json.dumps(filtered_data, sort_keys=True),
                    1 if is_security_sensitive else 0,
                ),
            )
            conn.commit()
        
        # Update last hash for chaining
        if is_security_sensitive:
            self._last_hash = entry_hash
        
        return entry_hash
    
    def _filter_sensitive_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Filter out sensitive fields that should never be logged.
        
        SECURITY BOUNDARY: Prevents accidental logging of:
        - Private keys
        - Secrets
        - Credentials
        - Passwords
        - Tokens
        """
        sensitive_keys = {
            'private_key',
            'secret',
            'password',
            'credential',
            'token',
            'api_key',
            'apikey',
            'auth_token',
            'signing_key',
            'private_key_pem',
        }
        
        filtered = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Skip exact matches
            if key_lower in sensitive_keys:
                continue
            
            # Skip partial matches containing sensitive substrings
            if any(s in key_lower for s in ['private', 'secret', 'password', 'credential']):
                continue
            
            # Recursively filter nested dicts
            if isinstance(value, dict):
                filtered[key] = self._filter_sensitive_fields(value)
            else:
                filtered[key] = value
        
        return filtered
    
    def _get_last_hash(self) -> Optional[str]:
        """Get the hash of the most recent security-sensitive entry."""
        if self._last_hash:
            return self._last_hash
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT entry_hash FROM audit_entries 
                WHERE is_security_sensitive = 1 
                ORDER BY id DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                self._last_hash = row['entry_hash']
                return self._last_hash
        
        return None
    
    def get_entries(
        self,
        run_id: Optional[str] = None,
        entry_type: Optional[AuditEntryType] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Query audit entries.
        
        Note: This is read-only, does not violate append-only guarantee.
        """
        query = "SELECT * FROM audit_entries WHERE 1=1"
        params = []
        
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        
        if entry_type:
            query += " AND entry_type = ?"
            params.append(entry_type.value)
        
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row['id'],
                    'entry_hash': row['entry_hash'],
                    'previous_hash': row['previous_hash'],
                    'timestamp': row['timestamp'],
                    'run_id': row['run_id'],
                    'user_id': row['user_id'],
                    'role': row['role'],
                    'entry_type': row['entry_type'],
                    'event_data': json.loads(row['event_data']),
                    'is_security_sensitive': bool(row['is_security_sensitive']),
                }
                for row in rows
            ]
    
    def verify_hash_chain(self) -> tuple[bool, list[str]]:
        """
        Verify integrity of hash chain.
        
        Returns:
            Tuple of (is_valid, list_of_tampered_entry_ids)
        """
        tampered = []
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, entry_hash, previous_hash, timestamp, entry_type, event_data
                FROM audit_entries 
                WHERE is_security_sensitive = 1 
                ORDER BY id ASC
                """
            )
            rows = cursor.fetchall()
        
        expected_previous = None
        
        for row in rows:
            # Recompute hash
            event_data = json.loads(row['event_data'])
            computed_hash = self._compute_entry_hash(
                row['timestamp'],
                row['entry_type'],
                event_data,
                row['previous_hash'],
            )
            
            if computed_hash != row['entry_hash']:
                tampered.append(str(row['id']))
            
            # Verify chain linkage
            if row['previous_hash'] != expected_previous and expected_previous is not None:
                if row['id'] not in tampered:
                    tampered.append(str(row['id']))
            
            expected_previous = row['entry_hash']
        
        return len(tampered) == 0, tampered
