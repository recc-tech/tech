@ECHO OFF
@TITLE Startup

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

./update_scripts.bat
./mcr_setup.bat
