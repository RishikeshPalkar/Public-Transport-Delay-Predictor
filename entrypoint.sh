#!/bin/sh
set -e

echo "[Docker Entrypoint] Starting..."

# Wait for MySQL database container
echo "[Docker Entrypoint] Waiting for database at $DB_HOST:$DB_PORT..."
python -c "
import socket
import time
import sys
import os

db_host = os.getenv('DB_HOST', 'db')
db_port = int(os.getenv('DB_PORT', 3306))

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
for i in range(30):
    try:
        s.connect((db_host, db_port))
        print(f'[Docker Entrypoint] Connected to database at {db_host}:{db_port}!')
        sys.exit(0)
    except (socket.error, socket.timeout):
        print(f'[Docker Entrypoint] Database not ready yet ({i+1}/30)...')
        time.sleep(2)
print('[Docker Entrypoint] Could not connect to database!')
sys.exit(1)
"

# Run Ingestion Pipeline to seed and setup database tables
echo "[Docker Entrypoint] Running data ingestion pipeline..."
python src/data_pipeline/ingest.py

# Check if model files exist; if not, train them!
if [ ! -f "models/departure_delay_xgb.json" ] || [ ! -f "models/arrival_delay_xgb.json" ]; then
    echo "[Docker Entrypoint] Models not found! Running model training pipeline..."
    python src/ml/train.py
else
    echo "[Docker Entrypoint] Pre-trained models found, skipping training."
fi

# Launch API using Uvicorn
echo "[Docker Entrypoint] Starting FastAPI REST API..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
