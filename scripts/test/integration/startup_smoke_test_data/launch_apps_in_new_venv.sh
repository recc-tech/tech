#!/bin/bash

set -ue

source "$(dirname "$(readlink -f "$0")")/define_helpers.sh"
move_to_scripts_dir
create_and_activate_venv './test/manual/.venv'
# TODO: Replace this with a special setup/requirements-launch-apps.txt file
pip install -r setup/requirements.txt 2>&1 > /dev/null
use_null_keyring
python launch_apps.py --help
