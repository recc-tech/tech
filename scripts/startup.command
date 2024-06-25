#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

./update_scripts.command
./download_pco_assets.command --auto-close &
./summarize_plan.command      --auto-close &
