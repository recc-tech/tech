@ECHO OFF
@TITLE Startup

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
