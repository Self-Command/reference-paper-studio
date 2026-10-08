#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && -n "${GITHUB_RUN_ID:-}" ]] || { echo CLOUD_ONLY; exit 2; }
sudo apt-get update -qq
mapfile -t packages < ci/system-packages.lock
sudo apt-get install -y --no-install-recommends "${packages[@]}"
mkdir -p build
dpkg-query -W > build/system-versions.txt
pip freeze > build/python-versions.txt
