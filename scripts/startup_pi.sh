#!/bin/bash

function main {
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
}

log_dir="$HOME/Logs"
mkdir -p "$log_dir"
log_file="$log_dir/$(date +%Y%m%d%H%M%S) startup_pi.log"
main 2>&1 | tee "$log_file"
