# scripts

## Organization

Note the following important files:

- _Top-level .py files._ These are command-line programs that can be run to perform common tasks, such as generating backup slides.
	- Run `foo.py` using `python foo.py`.
	- See the description and extra options for `foo.py` by running `python foo.py --help`.
- _Top-level .bat files._ For each top-level Python file (e.g., `foo.py`) there should be a corresponding batch file (e.g., `run_foo.bat`) that can be run from any directory to run the corresponding Python script. This is useful for creating desktop shortcuts.
- Subdirectories._ Code required by the top-level Python scripts is organized into packages (i.e., subdirectories). Each one should have a file `__init__.py` that summarizes the purpose of that package.
- `/test/`. These are tests to ensure the scripts work as expected. Run them all using `python -m unittest` or run specific tests using `python -m unittest discover -t . -s <PATH-TO-TESTS>`.
	- `/test/unit`. These are "unit tests" - they test individual software components and avoid side-effects like accessing the file system or the Internet.
	- `/test/integration`. These are "integration tests" - they test multiple components or have side-effects like accessing the file system or the Internet. As a result, they tend to be slower.

## Getting Started on a New Machine

1. Install Python. The scripts were developed and tested using Python 3.10.
2. Install the required external libraries by running `pip install -r requirements.txt`
3. Set up the computer to run `run_scripts_update.bat` on startup.
4. Create a desktop shortcut for each .bat file.
