@ECHO OFF
@TITLE Undo Updates

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

python undo_updates.py
