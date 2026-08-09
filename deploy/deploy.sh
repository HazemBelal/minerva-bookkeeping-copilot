#!/usr/bin/env bash
set -euo pipefail
cd /opt/minerva
source /etc/minerva-compose.env

git pull --ff-only

# deploy/nginx.conf is a plain-HTTP base (see the comment in that file) so it
# can start nginx on a box that has never run certbot. Once certbot has run,
# it rewrites /etc/nginx/conf.d/minerva.conf in place to add the TLS block --
# copying the repo's HTTP-only base over that file on every deploy would
# silently drop the live site back to plain HTTP, so only install it when no
# certificate exists yet. After certbot has run, certbot owns that file; we
# just reload nginx to pick up whatever's already there.
CERT=/etc/letsencrypt/live/srv1083267.hstgr.cloud/fullchain.pem
if [ ! -f "$CERT" ]; then
  cp deploy/nginx.conf /etc/nginx/conf.d/minerva.conf
fi

# `nginx -t && systemctl reload nginx` would NOT trip `set -e` on a failing
# test -- a command failing on the left of `&&` doesn't trigger errexit, so
# the script would silently skip the reload and fall through to bringing the
# containers up, exiting 0 as if the deploy succeeded on a broken config.
nginx -t || { echo "nginx config test failed" >&2; exit 1; }
systemctl reload nginx

# The runs volume shadows /app/runs inside the image, so the committed
# golden run has to be copied into the host-side volume to be visible.
mkdir -p data/runs
if [ -d backend/runs/golden ]; then
  rm -rf data/runs/golden
  cp -r backend/runs/golden data/runs/golden
fi

$COMPOSE up -d --build
$COMPOSE ps
