@ECHO OFF
@TITLE Summarize Vocals Notes

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

:: Start the command without a terminal window
start pythonw summarize_vocals_notes.py
wait_for_start.bat
