@ECHO OFF
@TITLE Update Scripts

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

git stash --include-untracked
git switch main
git pull

pip install --upgrade -r requirements.txt
