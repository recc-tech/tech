#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

python3 summarize_plan.py $* > /dev/null 2> /dev/null &
