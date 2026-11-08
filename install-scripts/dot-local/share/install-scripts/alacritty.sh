#!/usr/bin/env bash

set -euo pipefail

# check-brew: allow-unavailable
#
# The homebrew-cask `alacritty` cask is disabled because it does not pass the
# macOS Gatekeeper check, and `--no-quarantine` was removed in Homebrew 7.
# Prefer the cask when Homebrew can provision it; otherwise install the pinned
# upstream release after verifying its SHA256 and bundle identifier. Copying
# into /Applications needs no elevation (root:admin, mode 775).

ALACRITTY_VERSION="0.17.0"
# sha256 of Alacritty-v${ALACRITTY_VERSION}.dmg, from GitHub's release assets.
ALACRITTY_SHA256="ad8d7de35fb38e43184776cac6dfee05ca325caa0b6639a06a55e54e4b026620"

if brew list --cask alacritty >/dev/null 2>&1 && [[ -d /Applications/Alacritty.app ]]; then
	exit 0
fi
if brew install --cask alacritty 2>/dev/null &&
	brew list --cask alacritty >/dev/null 2>&1 &&
	[[ -d /Applications/Alacritty.app ]]; then
	exit 0
fi

echo "alacritty cask unavailable; falling back to the pinned upstream release" >&2

url="https://github.com/alacritty/alacritty/releases/download/v${ALACRITTY_VERSION}/Alacritty-v${ALACRITTY_VERSION}.dmg"

curl_opts=(--proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL)
# Avoid the compromised system trust store when Homebrew's bundle is available.
if [[ -f /opt/homebrew/etc/ca-certificates/cert.pem ]]; then
	curl_opts+=(--cacert /opt/homebrew/etc/ca-certificates/cert.pem)
fi

tmpdir=$(mktemp -d)
mountpoint="$tmpdir/mnt"
cleanup() {
	hdiutil detach "$mountpoint" -quiet 2>/dev/null || true
	rm -rf "$tmpdir"
}
trap cleanup EXIT

dmg="$tmpdir/Alacritty-v${ALACRITTY_VERSION}.dmg"
curl "${curl_opts[@]}" "$url" -o "$dmg"

printf '%s  %s\n' "$ALACRITTY_SHA256" "$dmg" | shasum -a 256 -c -

mkdir -p "$mountpoint"
hdiutil attach "$dmg" -nobrowse -quiet -mountpoint "$mountpoint"

app="$mountpoint/Alacritty.app"
bundle_id=$(/usr/libexec/PlistBuddy \
	-c 'Print :CFBundleIdentifier' "$app/Contents/Info.plist" 2>/dev/null || true)
if [[ $bundle_id != "org.alacritty" ]]; then
	echo "unexpected bundle identifier in the Alacritty DMG: ${bundle_id:-<none>}" >&2
	exit 1
fi

# Stage the app, then swap it in with a rollback if the copy fails.
staged="$tmpdir/Alacritty.app"
cp -R "$app" "$staged"

target="/Applications/Alacritty.app"
previous="/Applications/Alacritty.app.previous"
rm -rf "$previous"
if [[ -d $target ]]; then
	mv "$target" "$previous"
fi
if ! cp -R "$staged" "$target"; then
	rm -rf "$target"
	if [[ -d $previous ]]; then
		mv "$previous" "$target"
	fi
	exit 1
fi
rm -rf "$previous"
