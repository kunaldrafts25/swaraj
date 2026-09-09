#!/bin/bash
# SWARAJ v2 Setup Script
# Fail-closed: exits on any critical error

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

DATA_DIR="${SWARAJ_DATA_DIR:-$ROOT_DIR/data}"
KEYS_DIR="$DATA_DIR/keys"
AUDIT_DIR="$DATA_DIR/audit"
WORKSPACE_DIR="$DATA_DIR/workspace"
ARTIFACTS_DIR="$DATA_DIR/artifacts"
LOGS_DIR="${SWARAJ_LOGS_DIR:-$ROOT_DIR/logs}"
MODELS_DIR="$ROOT_DIR/models"

MODEL_FILENAME="qwen3-4b-instruct-q4_k_m.gguf"
MODEL_PATH="$MODELS_DIR/$MODEL_FILENAME"

# Parse arguments
REGENERATE_KEYS=false
SKIP_MODEL_CHECK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --regenerate-keys)
            REGENERATE_KEYS=true
            shift
            ;;
        --skip-model-check)
            SKIP_MODEL_CHECK=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --regenerate-keys   Regenerate Ed25519 keypair (overwrites existing)"
            echo "  --skip-model-check  Skip model artifact verification"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

log_info "SWARAJ v2 Setup Script"
log_info "======================"

# Step 1: Check required system dependencies
log_info "Checking system dependencies..."

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command not found: $1"
        log_error "Please install it and re-run setup."
        exit 1
    fi
}

check_command python3
check_command pip3

# Check for optional but recommended commands
if ! command -v docker &> /dev/null; then
    log_warn "Docker not found. Sandbox execution will use subprocess fallback."
fi

if ! command -v poppler-config &> /dev/null && ! command -v pdfinfo &> /dev/null; then
    log_warn "Poppler utilities not found. PDF ingestion will fail."
    log_warn "Install: sudo apt-get install poppler-utils (Debian/Ubuntu)"
fi

# Step 2: Create required directories
log_info "Creating directories..."

mkdir -p "$KEYS_DIR" "$AUDIT_DIR" "$WORKSPACE_DIR" "$ARTIFACTS_DIR" "$LOGS_DIR" "$MODELS_DIR"

# Set secure permissions on keys directory
chmod 700 "$KEYS_DIR"

# Create .gitkeep files for Git tracking
for dir in "$WORKSPACE_DIR" "$ARTIFACTS_DIR" "$MODELS_DIR"; do
    touch "$dir/.gitkeep" 2>/dev/null || true
done

# Step 3: Python environment and dependencies
log_info "Installing Python dependencies..."

pip3 install -e ".[dev]" --quiet

# Step 4: Model artifact verification
log_info "Checking model artifact..."

if [ "$SKIP_MODEL_CHECK" = true ]; then
    log_warn "Skipping model artifact check (--skip-model-check flag used)"
else
    if [ ! -f "$MODEL_PATH" ]; then
        log_error "Model artifact not found: $MODEL_PATH"
        log_error ""
        log_error "To proceed, you must:"
        log_error "  1. Download qwen3-4b-instruct-q4_k_m.gguf from HuggingFace"
        log_error "  2. Place it in: $MODELS_DIR/"
        log_error "  3. Re-run this setup script"
        log_error ""
        log_error "HuggingFace URL (verify checksum before use):"
        log_error "  https://huggingface.co/Qwen/Qwen3-4B-Instruct-GGUF"
        log_error ""
        log_error "FAIL-CLOSED: Cannot proceed without verified model artifact."
        exit 1
    fi

    # Calculate SHA256
    log_info "Calculating model SHA256 checksum..."
    CALCULATED_SHA256=$(sha256sum "$MODEL_PATH" | awk '{print $1}')
    log_info "Calculated SHA256: $CALCULATED_SHA256"

    # Check manifest for expected checksum
    MANIFEST_PATH="$ROOT_DIR/src/swaraj/registry/manifests/qwen3-4b.yaml"
    if [ -f "$MANIFEST_PATH" ]; then
        EXPECTED_SHA256=$(grep "^sha256:" "$MANIFEST_PATH" | awk '{print $2}' | tr -d '"' || echo "")
        
        if [ -n "$EXPECTED_SHA256" ] && [ "$EXPECTED_SHA256" != "PLACEHOLDER_CHECKSUM_DO_NOT_USE" ]; then
            if [ "$CALCULATED_SHA256" != "$EXPECTED_SHA256" ]; then
                log_error "Checksum mismatch!"
                log_error "  Expected: $EXPECTED_SHA256"
                log_error "  Got:      $CALCULATED_SHA256"
                log_error "Model artifact may be corrupted or incorrect version."
                log_error "FAIL-CLOSED: Refusing to continue with unverified model."
                exit 1
            else
                log_info "Checksum verified successfully."
            fi
        else
            log_warn "Manifest contains placeholder checksum."
            log_warn "Recorded calculated checksum for operator review:"
            log_warn "  sha256: $CALCULATED_SHA256"
            log_warn "Update the manifest with this value after operator verification."
        fi
    fi
fi

# Step 5: Initialize SQLite audit database
log_info "Initializing audit database..."

python3 << 'PYEOF'
import sqlite3
from pathlib import Path
import os

audit_dir = Path(os.environ.get('SWARAJ_AUDIT_DIR', 'data/audit'))
db_path = audit_dir / 'audit.db'

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Create audit_log table (append-only by design)
cursor.execute('''
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    user_id TEXT,
    role TEXT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,
    previous_hash TEXT,
    entry_hash TEXT NOT NULL
)
''')

# Create index for efficient lookups
cursor.execute('CREATE INDEX IF NOT EXISTS idx_run_id ON audit_log(run_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)')

conn.commit()
conn.close()

print(f"Audit database initialized: {db_path}")
PYEOF

# Step 6: Generate Ed25519 keypair
log_info "Setting up cryptographic keys..."

PRIVATE_KEY_PATH="$KEYS_DIR/private_key.bin"
PUBLIC_KEY_PATH="$KEYS_DIR/public_key.pem"

if [ -f "$PRIVATE_KEY_PATH" ]; then
    if [ "$REGENERATE_KEYS" = true ]; then
        log_warn "Existing private key found. Regenerating (--regenerate-keys flag used)..."
        rm -f "$PRIVATE_KEY_PATH" "$PUBLIC_KEY_PATH"
    else
        log_info "Existing private key found. Preserving (use --regenerate-keys to overwrite)."
    fi
fi

if [ ! -f "$PRIVATE_KEY_PATH" ]; then
    log_info "Generating new Ed25519 keypair..."
    
    python3 << 'PYEOF'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path
import os
import sys

keys_dir = Path(os.environ.get('SWARAJ_KEYS_DIR', 'data/keys'))
private_key_path = keys_dir / 'private_key.bin'
public_key_path = keys_dir / 'public_key.pem'

# Generate keypair
private_key = Ed25519PrivateKey.generate()

# Serialize private key (raw bytes for compact storage)
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption()
)

# Serialize public key (PEM for readability)
public_bytes = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Write with secure permissions
umask_original = os.umask(0o077)
try:
    private_key_path.write_bytes(private_bytes)
    public_key_path.write_bytes(public_bytes)
finally:
    os.umask(umask_original)

# Set explicit permissions (redundant but clear)
os.chmod(private_key_path, 0o600)
os.chmod(public_key_path, 0o644)

print(f"Private key generated: {private_key_path} (permissions: 600)")
print(f"Public key generated: {public_key_path} (permissions: 644)")
print("SECURITY: Private key never logged, never transmitted, never exposed via API.")
PYEOF
else
    log_info "Private key already exists. Skipping generation."
fi

# Verify key permissions
KEY_PERMS=$(stat -c %a "$PRIVATE_KEY_PATH" 2>/dev/null || stat -f %Lp "$PRIVATE_KEY_PATH" 2>/dev/null || echo "unknown")
if [ "$KEY_PERMS" != "600" ]; then
    log_warn "Private key permissions are $KEY_PERMS, should be 600. Fixing..."
    chmod 600 "$PRIVATE_KEY_PATH"
fi

# Step 7: Initialize configuration
log_info "Initializing configuration..."

cat > "$ROOT_DIR/.env.local" << 'ENVEOF'
# SWARAJ Local Configuration
# Generated by setup.sh - DO NOT COMMIT TO GIT

SWARAJ_ENV=development
SWARAJ_LOG_LEVEL=INFO
SWARAJ_DATA_DIR=data
SWARAJ_WORKSPACE_DIR=data/workspace
SWARAJ_KEYS_DIR=data/keys
SWARAJ_AUDIT_DIR=data/audit
SWARAJ_MODELS_DIR=models
ENVEOF

log_info "Configuration written to .env.local (not tracked by Git)"

# Step 8: Basic health check
log_info "Running basic health check..."

python3 << 'PYEOF'
import sys
from pathlib import Path

# Import test
try:
    from swaraj.api.main import app
    print("✓ Application imports successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Directory checks
required_dirs = ['data/keys', 'data/audit', 'data/workspace', 'data/artifacts', 'logs']
for dir_name in required_dirs:
    if Path(dir_name).is_dir():
        print(f"✓ Directory exists: {dir_name}")
    else:
        print(f"✗ Directory missing: {dir_name}")
        sys.exit(1)

# Key file checks
private_key = Path('data/keys/private_key.bin')
if private_key.exists():
    print(f"✓ Private key exists: {private_key}")
    # Check permissions
    import stat
    perms = oct(private_key.stat().st_mode)[-3:]
    if perms == '600':
        print(f"✓ Private key permissions correct: {perms}")
    else:
        print(f"✗ Private key permissions incorrect: {perms} (should be 600)")
        sys.exit(1)
else:
    print(f"✗ Private key missing: {private_key}")
    sys.exit(1)

print("\n✓ Health check passed")
PYEOF

# Step 9: Final summary
echo ""
log_info "=========================="
log_info "SWARAJ v2 Setup Complete"
log_info "=========================="
echo ""
log_info "Next steps:"
echo "  1. If model was missing, download it and re-run setup"
echo "  2. Review and update src/swaraj/registry/manifests/qwen3-4b.yaml with actual SHA256"
echo "  3. Run: docker compose up --build"
echo "  4. Or run locally: python -m uvicorn swaraj.api.main:app --host 127.0.0.1 --port 8000"
echo ""
log_info "Security reminders:"
echo "  - Private key stored at: $PRIVATE_KEY_PATH (permissions: 600)"
echo "  - Never commit private key to Git"
echo "  - Never share private key"
echo "  - Model artifact must be verified before production use"
echo ""

exit 0
