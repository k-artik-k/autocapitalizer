#!/usr/bin/env bash
# Build a native macOS .app and a drag-to-Applications DMG on macOS.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1:-2.1.0}"
target_arch="${TARGET_ARCH:-$(uname -m)}"
venv_dir="$project_root/.venv-macos"
release_dir="$project_root/dist/macos"
app_path="$release_dir/WhatsAppCapitalize.app"
dmg_path="$release_dir/WhatsAppCapitalize-${version}-macos-${target_arch}.dmg"
stage_dir=""
iconset_dir=""
icon_path="$project_root/build/macos/WhatsAppCapitalize.icns"

case "$target_arch" in
  arm64|x86_64|universal2) ;;
  *)
    echo "TARGET_ARCH must be arm64, x86_64, or universal2 (got: $target_arch)." >&2
    exit 2
    ;;
esac

cleanup() {
  [[ -n "$stage_dir" && -d "$stage_dir" ]] && rm -rf "$stage_dir"
  [[ -n "$iconset_dir" && -d "$iconset_dir" ]] && rm -rf "$iconset_dir"
}
trap cleanup EXIT

create_icns() {
  local icon_source="$project_root/assets/icon.png"
  iconset_dir="$(mktemp -d "${TMPDIR:-/tmp}/WhatsAppCapitalize.iconset.XXXXXX")/WhatsAppCapitalize.iconset"
  mkdir -p "$iconset_dir" "$(dirname "$icon_path")"

  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$icon_source" --out "$iconset_dir/icon_${size}x${size}.png" >/dev/null
    sips -z "$((size * 2))" "$((size * 2))" "$icon_source" \
      --out "$iconset_dir/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$iconset_dir" -o "$icon_path"
}

python3 -m venv "$venv_dir"
source "$venv_dir/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$project_root/requirements/macos.txt"
create_icns

pyinstaller_args=(
  --noconfirm
  --clean
  --onedir
  --windowed
  --name WhatsAppCapitalize
  --icon "$icon_path"
  --osx-bundle-identifier com.whatsappcapitalise.app
  --target-architecture "$target_arch"
  --paths "$project_root/src"
  --distpath "$release_dir"
  --workpath "$project_root/build/macos"
  --specpath "$project_root/build/spec"
  --hidden-import whatsapp_capitalize.macos_app
  "$project_root/src/whatsapp_capitalize/__main__.py"
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
