#!/bin/bash

day_of_week="$(date +'%A')"
if [[ "$day_of_week" != "Sunday" ]]; then
	echo "Exiting because it is $day_of_week, not Sunday."
	exit 0
fi

# Go to the scripts directory
cd "$(dirname "$0")"

./update_scripts.command
./launch_apps.command         --auto-close &
./download_pco_assets.command --auto-close &
./summarize_plan.command      --auto-close &
