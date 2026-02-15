#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

python3 apply_cam_settings.py $* &
