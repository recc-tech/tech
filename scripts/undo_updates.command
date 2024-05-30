#!/bin/bash

set -u

LATEST="latest"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RESET_COLOR='\033[0m'

echo "AVAILABLE VERSIONS:"
echo " * latest"
git tag --list | sort --reverse | head -n 5 | sed -rn 's/(.*)/ * \1/p'

echo
echo "SELECT THE VERSION TO USE:"
echo -n "> "
read -r tag

if [[ "$tag" = "latest" ]]; then
	gitmsg="$( git switch main 2>&1 )"
	if [[ "$?" != "0" ]]; then
		echo -e "${YELLOW}${gitmsg}${RESET_COLOR}"
		echo -e "${RED}Failed to switch to the latest version due to an unexpected error.${RESET_COLOR}"
	else
		echo -e "${GREEN}OK: currently on the latest version.${RESET_COLOR}"
	fi
	exit
fi

gitmsg="$( git checkout "tags/$tag" 2>&1 )"
if [[ "$?" != "0" ]]; then
	echo -e "${YELLOW}${gitmsg}${RESET_COLOR}"
	echo -e "${RED}Failed to switch to the selected version. Are you sure you selected a valid one?${RESET_COLOR}"
	exit
fi

current_tag="$( git describe 2>&1 )"
if [[ "$?" != "0" ]]; then
	echo -e "${YELLOW}${current_tag}${RESET_COLOR}"
	echo -e "${RED}Switching versions seemed to work, but now I can't tell which version we're currently on...${RESET_COLOR}"
	exit
fi

echo -e "${GREEN}OK: currently on version ${current_tag}${RESET_COLOR}"
