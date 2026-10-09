#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && -n "${GITHUB_RUN_ID:-}" ]] || { echo CLOUD_ONLY; exit 2; }
sudo apt-get update -qq
mapfile -t packages < ci/system-packages.lock
sudo apt-get install -y --no-install-recommends "${packages[@]}"
download_cache="${RPS_DOWNLOAD_CACHE:-.tool-downloads}"
mkdir -p "$download_cache"
pandoc_archive="$download_cache/pandoc-3.12.1-1-amd64.deb"
if [[ ! -f "$pandoc_archive" ]]; then
  curl --fail --location --retry 3 --connect-timeout 20 --max-time 180 https://github.com/jgm/pandoc/releases/download/3.12.1/pandoc-3.12.1-1-amd64.deb -o "$pandoc_archive"
fi
printf '%s  %s\n' 'b4217ac7c54067c442f9d4cd38bcd0c184a43f3e7053431a12263a6f92a33ba2' "$pandoc_archive" | sha256sum --check
sudo dpkg -i "$pandoc_archive"
mkdir -p build
dpkg-query -W > build/system-versions.txt
pip freeze > build/python-versions.txt
pandoc --version > build/pandoc-version.txt
cals_file="$(kpsewhich cals.sty)"
grep -q 'CALS tables v.2.4.2' "$cals_file" || { echo 'CALS_VERSION_MISMATCH'; exit 2; }
sha256sum "$cals_file" > build/cals-version.sha256
cuted_file="$(kpsewhich cuted.sty)"
grep -q '2021/10/04 v2.0' "$cuted_file" || { echo 'CUTED_VERSION_MISMATCH'; exit 2; }
sha256sum "$cuted_file" > build/cuted-version.sha256
# The distribution's 24.2 OMML importer corrupts some native scripts/brackets.
# Use a pinned upstream build in parallel; verify the official SHA-256.
lo_archive=LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz
if [[ ! -f "$download_cache/$lo_archive" ]]; then
  curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 "https://download.documentfoundation.org/libreoffice/stable/26.8.1/deb/x86_64/$lo_archive" -o "$download_cache/$lo_archive"
fi
printf '%s  %s\n' '30903df3b9f61360d9660cd707de48cd2831469114492a5008ed58a0ac77d044' "$download_cache/$lo_archive" | sha256sum --check
sha256sum "$download_cache/$lo_archive" > build/libreoffice-upstream.sha256
mkdir -p build/lo-install
tar -xzf "$download_cache/$lo_archive" -C build/lo-install
sudo dpkg -i build/lo-install/*/DEBS/*.deb
sudo ln -sf /opt/libreoffice26.8/program/soffice /usr/local/bin/libreoffice
libreoffice --version > build/libreoffice-version.txt
# Keep delivery artifacts small; package provenance remains in the manifests.
rm -r build/lo-install
