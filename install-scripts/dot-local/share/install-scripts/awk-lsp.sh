#!/usr/bin/env bash

brew info node && brew install node
brew unlink node && brew link node
npm install -g "awk-language-server@>=0.5.2"
