#!/bin/bash

function main {
	day_of_week="$(date +'%A')"
	if [[ "$day_of_week" != "Sunday" ]]; then
		echo "Exiting because it is $day_of_week, not Sunday."
		exit 0
	fi

	# Some apps (e.g., Firefox, Spotify) are installed via Brew
	brew upgrade

	# Go to the scripts directory
	cd "$0"

	python3 manage_config.py activate --profile foh
	./update_scripts.command
	./launch_apps.command         --auto-close &
	./download_pco_assets.command --auto-close &
	./summarize_plan.command      --auto-close &
}
export -f main

log_dir="$HOME/Documents/Logs"
mkdir -p "$log_dir"
log_file="$log_dir/$(date +%Y%m%d%H%M%S) startup_foh.log"
scripts_dir="$(dirname "$0")"
scripts_dir="$(readlink -f "$scripts_dir")"
nohup bash -c main "$scripts_dir" 2>&1 | tee "$log_file" &
