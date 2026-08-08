#!/usr/bin/env bash
set -euo pipefail
cd /opt/minerva
source /etc/minerva-compose.env

git pull --ff-only
cp deploy/nginx.conf /etc/nginx/conf.d/minerva.conf
nginx -t && systemctl reload nginx

# The runs volume shadows /app/runs inside the image, so the committed
# golden run has to be copied into the host-side volume to be visible.
mkdir -p data/runs
if [ -d backend/runs/golden ]; then
  rm -rf data/runs/golden
  cp -r backend/runs/golden data/runs/golden
fi

$COMPOSE up -d --build
$COMPOSE ps
