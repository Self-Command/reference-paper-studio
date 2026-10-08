#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && -n "${GITHUB_RUN_ID:-}" ]] || { echo CLOUD_ONLY; exit 2; }
sudo apt-get update -qq
mapfile -t packages < ci/system-packages.lock
sudo apt-get install -y --no-install-recommends "${packages[@]}"
curl --fail --location --retry 3 --max-time 180 https://github.com/jgm/pandoc/releases/download/3.12.1/pandoc-3.12.1-1-amd64.deb -o /tmp/rps-pandoc.deb
printf '%s  %s\n' 'b4217ac7c54067c442f9d4cd38bcd0c184a43f3e7053431a12263a6f92a33ba2' /tmp/rps-pandoc.deb | sha256sum --check
sudo dpkg -i /tmp/rps-pandoc.deb
mkdir -p build
dpkg-query -W > build/system-versions.txt
pip freeze > build/python-versions.txt
pandoc --version > build/pandoc-version.txt
# The distribution's 24.2 OMML importer corrupts some native scripts/brackets.
# Use a pinned upstream build in parallel; verify the official SHA-256.
lo_archive=LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz
curl --fail --location --retry 3 --max-time 300 "https://download.documentfoundation.org/libreoffice/stable/26.8.1/deb/x86_64/$lo_archive" -o "build/$lo_archive"
printf '%s  %s\n' '30903df3b9f61360d9660cd707de48cd2831469114492a5008ed58a0ac77d044' "build/$lo_archive" | sha256sum --check
sha256sum "build/$lo_archive" > build/libreoffice-upstream.sha256
mkdir -p build/lo-install
tar -xzf "build/$lo_archive" -C build/lo-install
sudo dpkg -i build/lo-install/*/DEBS/*.deb
sudo ln -sf /opt/libreoffice26.8/program/soffice /usr/local/bin/libreoffice
libreoffice --version > build/libreoffice-version.txt
# Keep delivery artifacts small; package provenance remains in the manifests.
rm -r build/lo-install
rm "build/$lo_archive"
