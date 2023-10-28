# scripts

## Organization

Note the following important files:

- _Top-level .py files._ These are command-line programs that can be run to perform common tasks, such as generating backup slides.
	- Run `foo.py` using `python foo.py`.
	- See the description and extra options for `foo.py` by running `python foo.py --help`.
- _Top-level .bat files._ For each top-level Python file (e.g., `foo.py`) there should be a corresponding batch file (e.g., `run_foo.py`) that can be run from any directory to run the corresponding Python script. This is useful for creating desktop shortcuts.
- Subdirectories._ Code required by the top-level Python scripts is organized into packages (i.e., subdirectories). Each one should have a file `__init__.py` that summarizes the purpose of that package.

## Getting Started on a New Machine

1. Install Python. The scripts were developed and tested using Python 3.10.
2. Install the required external libraries by running `pip install -r requirements.txt`
