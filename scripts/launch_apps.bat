@ECHO OFF
@TITLE Launch Apps

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

:: Start the command without a terminal window
start pythonw launch_apps.py pco boxcast cop vmix mcr_setup_checklist %*
wait_for_start.bat
