#!/bin/bash
# Prepare a project-local Python automatically, then launch the macOS preview.
set -euo pipefail

dsp_failure() {
    local dsp_status=$?
    if [ "$dsp_status" -ne 0 ]; then
        printf '\nDSP408FIR Control could not start. Keep this window and share the error above.\n'
        if [ -t 0 ]; then read -r -p 'Press Enter to close this window. ' || true; fi
    fi
}
trap dsp_failure EXIT

if [ "$(/usr/bin/uname -s)" != Darwin ]; then
    printf 'This launcher is for macOS only.\n' >&2
    exit 1
fi

dsp_arch=$(/usr/bin/uname -m)
# Use native Apple Silicon even if Terminal was started under Rosetta.
if [ "$dsp_arch" = x86_64 ] && [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || true)" = 1 ]; then
    exec /usr/bin/arch -arm64 /bin/bash "$0"
fi
case "$dsp_arch" in
    arm64)
        dsp_target=aarch64-apple-darwin
        dsp_uv_sha=cfe454573412ff7380d15fc7dae5997ab53ffce72fce0a78e91ddbc84001acd2
        ;;
    x86_64)
        dsp_target=x86_64-apple-darwin
        dsp_uv_sha=bb7b805bdcf3d0bc8c74ceb94569e6b3e8aa35bd492acdbb9d46bf46d9d4ff6b
        ;;
    *) printf 'Unsupported Mac architecture: %s\n' "$dsp_arch" >&2; exit 1 ;;
esac

dsp_os=$(/usr/bin/sw_vers -productVersion)
if ! /usr/bin/awk -v version="$dsp_os" 'BEGIN {split(version,v,"."); exit !(v[1]>14 || (v[1]==14 && v[2]>=4))}'; then
    printf 'This preview requires macOS 14.4 or newer. Found %s.\n' "$dsp_os" >&2
    exit 1
fi

cd -- "$(dirname "$0")"
dsp_root=$(pwd -P)
if [ ! -f "$dsp_root/main.py" ] || [ ! -f "$dsp_root/packaging/macos/requirements.txt" ]; then
    printf 'Keep START_MAC.command inside the extracted DSP408FIR-Control folder.\n' >&2
    exit 1
fi

dsp_bootstrap="$dsp_root/work/macos-bootstrap/$dsp_arch"
dsp_uv_version=0.13.1
dsp_uv="$dsp_bootstrap/uv-$dsp_uv_version/uv-$dsp_target/uv"
dsp_environment="$dsp_root/.venv-macos-auto"
dsp_python="$dsp_environment/bin/python"
mkdir -p "$dsp_bootstrap/uv-$dsp_uv_version"

printf '\nDSP408FIR Control - macOS preview\nFirst start downloads Python and libraries automatically. Please wait.\n\n'
if [ ! -x "$dsp_uv" ]; then
    dsp_archive=$(/usr/bin/mktemp "$dsp_bootstrap/uv-download.XXXXXX")
    /usr/bin/curl --fail --location --retry 2 --connect-timeout 15 --max-time 180 \
        "https://github.com/astral-sh/uv/releases/download/$dsp_uv_version/uv-$dsp_target.tar.gz" \
        --output "$dsp_archive"
    printf '%s  %s\n' "$dsp_uv_sha" "$dsp_archive" | /usr/bin/shasum -a 256 -c -
    /usr/bin/tar -xzf "$dsp_archive" -C "$dsp_bootstrap/uv-$dsp_uv_version" "uv-$dsp_target/uv"
    /bin/rm -f -- "$dsp_archive"
fi

# Do not install into system Python or alter shell profiles / PATH.
export UV_PYTHON_INSTALL_DIR="$dsp_bootstrap/python"
export UV_CACHE_DIR="$dsp_bootstrap/cache"
export UV_PYTHON_PREFERENCE=only-managed
export UV_NO_CONFIG=1
unset PYTHONHOME PYTHONPATH QT_PLUGIN_PATH QML_IMPORT_PATH QML2_IMPORT_PATH || true

if [ ! -x "$dsp_python" ]; then
    "$dsp_uv" venv --python 3.14.8 "$dsp_environment"
fi
"$dsp_python" -c 'import platform, sys; assert sys.version_info[:3] == (3,14,8); assert platform.machine() == sys.argv[1]; print("Python", platform.python_version(), platform.machine())' "$dsp_arch"

dsp_requirements="$dsp_root/packaging/macos/requirements.txt"
dsp_wanted=$(/usr/bin/shasum -a 256 "$dsp_requirements" | /usr/bin/awk '{print $1}')
dsp_marker="$dsp_bootstrap/requirements.sha256"
if [ "$(/bin/cat "$dsp_marker" 2>/dev/null || true)" != "$dsp_wanted" ] || \
   ! "$dsp_python" -c 'import PySide6.QtQuick, PySide6.QtSvg, hid' 2>/dev/null; then
    "$dsp_uv" pip install --python "$dsp_python" --only-binary :all: \
        --index-url https://pypi.org/simple --requirement "$dsp_requirements"
    printf '%s\n' "$dsp_wanted" > "$dsp_marker"
fi

printf '\nOpening the application...\n'
"$dsp_python" "$dsp_root/main.py"
