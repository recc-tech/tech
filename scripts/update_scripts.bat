@ECHO OFF
@TITLE Update Scripts

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

git stash --include-untracked
git switch main
git pull

pip install --upgrade -r ./setup/requirements.txt

ECHO(
ECHO Successfully updated scripts. You can now close this window.
PAUSE
