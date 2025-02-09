#!/bin/bash

day_of_week="$(date +'%A')"
if [[ "$day_of_week" != "Sunday" ]]; then
	echo "Exiting because it is $day_of_week, not Sunday."
	exit 0
fi

# Go to the scripts directory
cd "$(dirname "$0")"
source .venv/bin/activate

./update_scripts.command
python3 launch_apps.py pco_live --auto-close &
