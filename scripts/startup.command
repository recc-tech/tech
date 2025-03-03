#!/bin/bash

function main {
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
}

log_dir="$HOME/Documents/Logs"
mkdir -p "$log_dir"
log_file="$log_dir/$(date +%Y%m%d%H%M%S) startup_foh.log"
main 2>&1 | tee "$log_file"
