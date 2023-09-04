@ECHO OFF
@TITLE MCR Setup

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

python mcr_setup.py %*
