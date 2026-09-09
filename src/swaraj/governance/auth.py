"""
SWARAJ v2 - Production Identity Store
Replaces flat-file users.json with SQLite + Argon2id + JWT
"""
import sqlite3
import json
import os
import time
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from swaraj.config import settings

# Initialize Argon2id hasher (OWASP recommended settings)
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID
)

class AuthDatabase:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite schema for users, sessions, and lockouts."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Users table with Argon2id hashes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        """)
        
        # Sessions table for JWT tracking (revocation)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_jti TEXT UNIQUE NOT NULL,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_revoked BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        
        # Lockout table for rate limiting
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lockouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL, -- IP or username
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            UNIQUE(identifier)
        )
        """)
        
        # Audit log for auth events
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            username TEXT,
            success BOOLEAN NOT NULL,
            details TEXT,
            ip_address TEXT
        )
        """)
        
        conn.commit()
        conn.close()
    
    def create_user(self, username: str, password: str, role: str) -> bool:
        """Create user with Argon2id hashed password."""
        password_hash = ph.hash(password)
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, role)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def verify_password(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify password and return user info if valid."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        user_id, db_username, password_hash, role, is_active = row
        
        if not is_active:
            return None
        
        try:
            ph.verify(password_hash, password)
            # Update last login
            self._update_last_login(user_id)
            return {"id": user_id, "username": db_username, "role": role}
        except VerifyMismatchError:
            return None
        except InvalidHash:
            # Rehash needed? (Migration path)
            return None
    
    def _update_last_login(self, user_id: int):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def check_lockout(self, identifier: str) -> bool:
        """Return True if locked out."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT locked_until FROM lockouts WHERE identifier = ?",
            (identifier,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False
        
        locked_until = datetime.fromisoformat(row[0])
        if datetime.now() < locked_until:
            return True
        
        # Expired, clear it
        self._clear_lockout(identifier)
        return False
    
    def record_failed_attempt(self, identifier: str):
        """Record failed attempt and lockout if threshold reached."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Upsert logic
        cursor.execute("""
            INSERT INTO lockouts (identifier, failed_attempts, locked_until)
            VALUES (?, 1, NULL)
            ON CONFLICT(identifier) DO UPDATE SET
                failed_attempts = failed_attempts + 1,
                locked_until = CASE 
                    WHEN failed_attempts + 1 >= 5 THEN datetime('now', '+15 minutes')
                    ELSE locked_until 
                END
            WHERE identifier = ?
        """, (identifier, identifier))
        
        conn.commit()
        conn.close()
    
    def _clear_lockout(self, identifier: str):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lockouts WHERE identifier = ?", (identifier,))
        conn.commit()
        conn.close()
    
    def audit_event(self, event_type: str, username: str, success: bool, details: str = "", ip: str = ""):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO auth_audit (event_type, username, success, details, ip_address) VALUES (?, ?, ?, ?, ?)",
            (event_type, username, success, details, ip)
        )
        conn.commit()
        conn.close()

class AuthService:
    def __init__(self, db_path: str, private_key_path: str):
        self.db = AuthDatabase(db_path)
        self.private_key_path = Path(private_key_path)
        self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        """Load Ed25519 key for JWT signing or generate if missing."""
        if self.private_key_path.exists():
            with open(self.private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
            self.public_key = self.private_key.public_key()
        else:
            # Generate new keypair
            self.private_key = Ed25519PrivateKey.generate()
            pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.private_key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.private_key_path, "wb") as f:
                f.write(pem)
            os.chmod(str(self.private_key_path), 0o600)
            self.public_key = self.private_key.public_key()
    
    def login(self, username: str, password: str, ip: str = "") -> Optional[str]:
        """Authenticate and return JWT."""
        if self.db.check_lockout(username):
            self.db.audit_event("login", username, False, "Locked out", ip)
            raise PermissionError("Account locked due to too many failed attempts.")
        
        user = self.db.verify_password(username, password)
        
        if not user:
            self.db.record_failed_attempt(username)
            self.db.audit_event("login", username, False, "Invalid credentials", ip)
            return None
        
        # Generate JWT
        now = datetime.utcnow()
        expires = now + timedelta(minutes=15)
        jti = secrets.token_hex(16)
        
        payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
            "iat": now,
            "exp": expires,
            "jti": jti
        }
        
        token = jwt.encode(payload, self.private_key, algorithm="EdDSA")
        
        # Record session
        conn = sqlite3.connect(str(self.db.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (user_id, token_jti, expires_at) VALUES (?, ?, ?)",
            (user["id"], jti, expires.isoformat())
        )
        conn.commit()
        conn.close()
        
        self.db.audit_event("login", username, True, "Success", ip)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT and check revocation."""
        try:
            payload = jwt.decode(token, self.public_key, algorithms=["EdDSA"])
            
            # Check revocation
            conn = sqlite3.connect(str(self.db.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_revoked FROM sessions WHERE token_jti = ?",
                (payload["jti"],)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                return None
            
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def logout(self, token: str):
        """Revoke token."""
        try:
            payload = jwt.decode(token, self.public_key, algorithms=["EdDSA"])
            conn = sqlite3.connect(str(self.db.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET is_revoked = 1 WHERE token_jti = ?",
                (payload["jti"],)
            )
            conn.commit()
            conn.close()
        except jwt.InvalidTokenError:
            pass
