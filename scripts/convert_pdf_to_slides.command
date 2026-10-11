#!/bin/bash

# Go to the scripts directory
cd "$(dirname "$0")"

python3 convert_pdf_to_slides.py $* &
