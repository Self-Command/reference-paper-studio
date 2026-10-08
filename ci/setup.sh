#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && -n "${GITHUB_RUN_ID:-}" ]] || { echo CLOUD_ONLY; exit 2; }
sudo apt-get update -qq
mapfile -t packages < ci/system-packages.lock
sudo apt-get install -y --no-install-recommends "${packages[@]}"
mkdir -p build
dpkg-query -W > build/system-versions.txt
pip freeze > build/python-versions.txt
# The distribution's 24.2 OMML importer corrupts some native scripts/brackets.
# Use a versioned upstream build in parallel; checksum is recorded for locking.
lo_archive=LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz
curl --fail --location --retry 3 --max-time 300 "https://download.documentfoundation.org/libreoffice/stable/26.8.1/deb/x86_64/$lo_archive" -o "build/$lo_archive"
sha256sum "build/$lo_archive" > build/libreoffice-upstream.sha256
mkdir -p build/lo-install
tar -xzf "build/$lo_archive" -C build/lo-install
sudo dpkg -i build/lo-install/*/DEBS/*.deb
sudo ln -sf /opt/libreoffice26.8/program/soffice /usr/local/bin/libreoffice
libreoffice --version > build/libreoffice-version.txt
# Keep delivery artifacts small; package provenance remains in the manifests.
rm -r build/lo-install
rm "build/$lo_archive"
