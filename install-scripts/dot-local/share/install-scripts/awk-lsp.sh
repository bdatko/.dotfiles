#!/usr/bin/env bash

set -euo pipefail

brew install node
brew unlink node 2>/dev/null || true
brew link node
npm install -g "awk-language-server@>=0.5.2"
