# scripts

## Organization

Note the following important files:

- _Top-level .py files._ These are command-line programs that can be run to perform common tasks, such as generating backup slides.
	- Run `foo.py` using `python foo.py` or `pythonw foo.py`.
	- See the description and extra options for `foo.py` by running `python foo.py --help`.
- _Top-level batch files and shell scripts._ For each top-level Python file (e.g., `foo.py`) there should be a corresponding batch file (e.g., `foo.bat`) that can be run from any directory to run the corresponding Python script. Similarly, in some cases, there are shell scripts that can be run on macOS (e.g., `foo.command`). These are useful for creating desktop shortcuts.
- Subdirectories._ Code required by the top-level Python scripts is organized into packages (i.e., subdirectories). Each one should have a file `__init__.py` that summarizes the purpose of that package.
- `/test/`. These are tests to ensure the scripts work as expected. Run them all using `python -m unittest` or run specific tests using `python -m unittest discover -t . -s <PATH-TO-TESTS>`.
	- `/test/unit`. These are "unit tests" - they test individual software components and avoid side-effects like accessing the file system or the Internet.
	- `/test/integration`. These are "integration tests" - they test multiple components or have side-effects like accessing the file system or the Internet. As a result, they tend to be slower.

## Setting up a New Production Environment

1. Install Python. The scripts were developed and tested using Python 3.10.
2. Move to the `scripts/` directory.
3. Install the required external libraries by running `pip install -r requirements.txt`
4. Set up the computer to run `update_scripts.bat` (on Windows) or `update_scripts.command` (on macOS) on startup.
5. Create a desktop shortcut for each top-level script (batch files on Windows, shell scripts on macOS).
	- On Windows, run `New-Shortcuts.ps1` in PowerShell.
	- On macOS, run `make_shortcuts.sh` in bash. You may also need to grant the scripts execution permission using `chmod u+x <SCRIPT-NAME-HERE>`.
6. Activate the configuration profile by running `python manage_config.py activate`.

## Setting up a New Development Environment

1. Install Python. The scripts were developed and tested using Python 3.10.
2. Move to the `scripts/` directory.
3. Optionally create a new Python virtual environment using the command `python -m venv .venv`. Activate this virtual environment using `source .venv/bin/activate` on MacOS or `.venv/Scripts/activate` on Windows.
4. Install the required external libraries by running `pip install -r requirements.txt`
5. Install the required development dependencies (e.g., those required for testing but not when running the code in production) by running `pip install -r requirements-dev.txt`.
6. Activate the configuration profile by running `python manage_config.py activate --profile PROFILE`, where `PROFILE` should probably be one of `mcr_dev` or `foh_dev`. To see the full list of available profiles, run `python manage_config.py list`.
