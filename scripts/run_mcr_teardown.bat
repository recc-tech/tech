@ECHO OFF
@TITLE MCR Teardown

:: In some cases, cmd.exe opens in C:\Windows\System32. The user does not
:: normally have permission to modify files in that directory, which can cause
:: problems because the Selenium Firefox web driver tries to write to
:: geckodriver.log in the current working directory. Moving into the tech Git
:: repo should avoid permission issues.
CD %~dp0

python mcr_teardown.py

PAUSE
