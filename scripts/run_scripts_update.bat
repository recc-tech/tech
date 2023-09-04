@ECHO OFF
@TITLE Update Scripts

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

git pull
pip install --upgrade -r requirements.txt

ECHO(
ECHO Successfully updated scripts. You can now close this window.
PAUSE
