#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

python3 summarize_vocals_notes.py $* &
