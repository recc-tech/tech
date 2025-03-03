@ECHO OFF
@TITLE Startup

FOR /F "tokens=* USEBACKQ" %%F IN (`python -c "from datetime import datetime; print(datetime.now().strftime('%%Y%%m%%d%%H%%M%%S'))"`) DO (
	SET now=%%F
)
SET log_dir=D:\Users\Tech\Documents\Logs
SET log_file=%log_dir%\%now%_startup_mcr.log
ECHO Starting up...
ECHO Output of this batch file will be logged to %log_file%
CALL :main > "%log_file%" 2>&1
EXIT /B



:main
FOR /F "tokens=* USEBACKQ" %%F IN (`python -c "from datetime import date; print(date.today().strftime('%%A'))"`) DO (
	SET day_of_week=%%F
)
IF NOT "%day_of_week%" == "Sunday" (
	ECHO Exiting because it is %day_of_week%, not Sunday.
	EXIT 0
)

:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

CALL ./update_scripts.bat
CALL ./launch_apps.bat --auto-close
CALL ./mcr_setup.bat

EXIT /B
