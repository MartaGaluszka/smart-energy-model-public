#!/usr/bin/env bash
# Bootstrap Ubuntu na OCI: Docker Engine + Compose plugin.
# Uruchom NA VM (SSH): curl … | bash  LUB  bash bootstrap-vm.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Uruchom jako root (sudo bash bootstrap-vm.sh)" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg rsync

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
docker version
docker compose version
echo "OK — Docker gotowy. Dalej: sklonuj/rsync repo i docker compose -f deploy/oci/docker-compose.yml up -d --build"
