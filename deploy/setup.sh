#!/usr/bin/env bash
set -euo pipefail

# Minimal setup script for systemd + venv deployment
# Usage: run from repository root: sudo ./deploy/setup.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "Deploy root: $ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install Python 3 and retry." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Edit .env with real SECRET_KEY and DATABASE_URL, then rerun this script." >&2
    exit 1
  else
    echo ".env not found and no .env.example present. Create .env and retry." >&2
    exit 1
  fi
fi

echo "Applying Alembic migrations..."
alembic upgrade head

SERVICE_PATH="/etc/systemd/system/chronosync.service"
TMP_SERVICE="/tmp/chronosync.service"

cat > "$TMP_SERVICE" <<EOF
[Unit]
Description=ChronoSync FastAPI
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$ROOT_DIR
EnvironmentFile=$ROOT_DIR/.env
ExecStart=$ROOT_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

echo "Installing systemd service to $SERVICE_PATH (requires sudo)..."
sudo mv "$TMP_SERVICE" "$SERVICE_PATH"
sudo systemctl daemon-reload
sudo systemctl enable --now chronosync

echo "Deployment finished. Check service status: sudo systemctl status chronosync"
