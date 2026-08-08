#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-srv1083267.hstgr.cloud}"
EMAIL="${EMAIL:?set EMAIL=you@example.com}"

dnf -y install epel-release
dnf -y install git nginx certbot python3-certbot-nginx

# Docker. This box may already have it, and reinstalling would restart the
# daemon and bounce every running container, so only install if it is absent.
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "docker $(docker --version) and compose already present, leaving them alone"
  echo "COMPOSE=docker compose" >/etc/minerva-compose.env
else
  cat >/etc/yum.repos.d/docker-ce.repo <<'EOF'
[docker-ce-stable]
name=Docker CE Stable
baseurl=https://download.docker.com/linux/centos/$releasever/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=https://download.docker.com/linux/centos/gpg
EOF
  if dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin; then
    systemctl enable --now docker
    echo "COMPOSE=docker compose" >/etc/minerva-compose.env
  else
    echo "docker-ce has no package for this release; falling back to podman"
    rm -f /etc/yum.repos.d/docker-ce.repo
    dnf -y install podman podman-compose
    systemctl enable --now podman.socket
    echo "COMPOSE=podman-compose" >/etc/minerva-compose.env
  fi
fi

# When SELinux is enforcing, nginx cannot proxy to a local port until this
# boolean is set — the symptom is a 502 with "Permission denied" in the error
# log. When SELinux is disabled, setsebool exits non-zero and would abort this
# script under `set -e`, so the call is guarded rather than unconditional.
if [ "$(getenforce 2>/dev/null || echo Disabled)" != "Disabled" ]; then
  dnf -y install policycoreutils-python-utils
  setsebool -P httpd_can_network_connect 1
else
  echo "SELinux disabled; skipping httpd_can_network_connect"
fi

# Only touch the firewall if it is already running. Starting firewalld on a
# host that has been running without it applies a default zone policy that can
# cut off services which were reachable a moment earlier.
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-service=http
  firewall-cmd --permanent --add-service=https
  firewall-cmd --reload
else
  echo "firewalld inactive; leaving network policy untouched"
fi

install -d -m 700 /opt/minerva

cp /opt/minerva/deploy/nginx.conf /etc/nginx/conf.d/minerva.conf 2>/dev/null || true
systemctl enable --now nginx

echo "bootstrap complete for ${DOMAIN}"
