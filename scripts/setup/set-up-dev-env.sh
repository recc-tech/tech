#!/bin/bash

# IMPORTANT: Keep this script in sync with README.md

set -ue

cd "$(git rev-parse --show-toplevel)/scripts"
python3 -m venv .venv
source .venv/bin/activate
pip install -r setup/requirements-dev.txt
python manage_config.py activate --profile foh_dev
