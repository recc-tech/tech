@ECHO OFF
@TITLE Startup

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

CALL ./update_scripts.bat
CALL ./launch_apps.bat --auto-close
CALL ./mcr_setup.bat
