#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

python3 launch_apps.py pco foh_video_setup_checklist $* &
