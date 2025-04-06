#!/bin/bash

function main {
	day_of_week="$(date +'%A')"
	if [[ "$day_of_week" != "Sunday" ]]; then
		echo "Exiting because it is $day_of_week, not Sunday."
		exit 0
	fi

	scripts_dir="$(dirname "$(readlink -f "$0")")"
	cd "$scripts_dir"
	source .venv/bin/activate

	# tkinter needs the $DISPLAY environment variable
	export DISPLAY=':0'

	git stash --include-untracked
	git switch main
	git pull
	python3 -m pip install --upgrade pip
	python3 -m pip install --upgrade --upgrade-strategy eager -r ./setup/requirements-launch-apps.txt

	python3 manage_config.py activate --profile pi

	python3 launch_apps.py pco_live --auto-close &
}

log_dir="$HOME/Logs"
mkdir -p "$log_dir"
log_file="$log_dir/$(date +%Y%m%d%H%M%S) startup_pi.log"
main 2>&1 | tee "$log_file"
