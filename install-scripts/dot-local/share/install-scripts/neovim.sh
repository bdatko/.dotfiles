#!/usr/bin/env bash

set -euo pipefail

# Version this config is tested against; bump deliberately (see README).
expected=0.12.6

# `brew install` upgrades an outdated formula even when it is pinned, so only
# install when neovim is absent. Re-running this script must never change the
# installed version.
if ! brew list --versions neovim >/dev/null 2>&1; then
	brew install neovim
fi

if ! brew list --pinned | grep -qx neovim; then
	brew pin neovim
fi

installed=$(brew list --versions neovim | awk '{print $2}')
if [[ $installed != "$expected" ]]; then
	echo "warning: neovim $installed is installed; this repo expects $expected" >&2
	echo "to update deliberately: brew unpin neovim && brew upgrade neovim" >&2
fi
