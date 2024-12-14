#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

python3 download_pco_assets.py $* &
