#!/bin/bash

function move_to_scripts_dir {
	scripts_dir="$(git rev-parse --show-toplevel)/scripts"
	cd "$scripts_dir"
}

function create_and_activate_venv {
	venv_dir="$1"
	if [[ "$venv_dir" = "" ]]; then
		2>&1 echo "The path to the venv directory is empty."
		exit 1
	fi
	git clean -xdf "$venv_dir" 2>&1 > /dev/null
	if [[ -e "$venv_dir" ]]; then
		2>&1 echo "The venv directory still exists."
		exit 1
	fi
	if [[ ! -d "$(dirname "$venv_dir")" ]]; then
		2>&1 echo "The parent of the venv directory does not exist or is not a directory."
		exit 1
	fi

	python -m venv "$venv_dir"
	source "$venv_dir/bin/activate"
	# In case pip is out of date (which would cause a warning to be printed and
	# make the tests fail)
	pip install --upgrade pip 2>&1 > /dev/null
}

function use_null_keyring {
	# Make sure we don't accidentally use credentials
	export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
	python -c 'import keyring; import keyring.backends.null; assert isinstance(keyring.get_keyring(), keyring.backends.null.Keyring)'
}
