#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

git stash --include-untracked
git switch main
git pull

python3 -m pip install --upgrade pip
python3 -m pip install --upgrade --upgrade-strategy eager -r ./setup/requirements.txt
