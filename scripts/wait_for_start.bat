@echo off

echo This will be deleted once the script starts.> startup.txt
echo Please wait, the script is starting...

:loop
python -c "import time; time.sleep(0.1)"
if exist startup.txt (
	goto loop
)
