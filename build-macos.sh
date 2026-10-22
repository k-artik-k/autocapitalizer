#!/usr/bin/env bash
# Build a native macOS .app and a drag-to-Applications DMG on macOS.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
version="${1:-1.0.0}"
target_arch="${TARGET_ARCH:-$(uname -m)}"
venv_dir="$project_root/.venv-macos"
release_dir="$project_root/release"
app_path="$project_root/dist/WhatsAppCapitalize.app"
dmg_path="$release_dir/WhatsAppCapitalize-${version}-macos-${target_arch}.dmg"
stage_dir=""

case "$target_arch" in
  arm64|x86_64|universal2) ;;
  *)
    echo "TARGET_ARCH must be arm64, x86_64, or universal2 (got: $target_arch)." >&2
    exit 2
    ;;
esac

cleanup() {
  [[ -n "$stage_dir" && -d "$stage_dir" ]] && rm -rf "$stage_dir"
}
trap cleanup EXIT

python3 -m venv "$venv_dir"
source "$venv_dir/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$project_root/requirements-macos.txt"

pyinstaller_args=(
  --noconfirm
  --clean
  --onedir
  --windowed
  --name WhatsAppCapitalize
  --icon "$project_root/icon.ico"
  --osx-bundle-identifier com.whatsappcapitalise.app
  --target-architecture "$target_arch"
  --hidden-import macos_app
  "$project_root/wa_capitalize.py"
)

# Provide a Developer ID Application identity to produce a distributable signed
# app. Without it PyInstaller applies ad-hoc signing, which Gatekeeper warns about.
if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  pyinstaller_args+=(--codesign-identity "$CODESIGN_IDENTITY")
fi

python -m PyInstaller "${pyinstaller_args[@]}"

if [[ ! -d "$app_path" ]]; then
  echo "Expected app bundle was not created: $app_path" >&2
  exit 1
fi

if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  codesign --verify --deep --strict --verbose=2 "$app_path"
fi

mkdir -p "$release_dir"
stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/WhatsAppCapitalize.XXXXXX")"
ditto "$app_path" "$stage_dir/WhatsAppCapitalize.app"
ln -s /Applications "$stage_dir/Applications"
hdiutil create -volname "WhatsApp Capitalise" -srcfolder "$stage_dir" \
  -ov -format UDZO "$dmg_path"

echo "macOS app bundle: $app_path"
echo "macOS installer DMG: $dmg_path"
