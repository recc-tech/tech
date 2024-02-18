#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

git stash --include-untracked
git switch main
git pull

pip install --upgrade -r requirements.txt

echo Successfully updated scripts. Press any key to exit.
read -r REPLY
