@ECHO OFF
@TITLE Update Scripts

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

git stash --include-untracked
git switch main
git pull

python -m pip install --upgrade pip
python -m pip install --upgrade -r ./setup/requirements.txt
