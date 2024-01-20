@ECHO OFF
@TITLE Download PCO Assets

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

:: Start the command without a terminal window
start pythonw download_pco_assets.py
