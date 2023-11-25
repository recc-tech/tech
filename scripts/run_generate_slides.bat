@ECHO OFF
@TITLE Generate Slides

:: In some cases, cmd.exe opens in C:\Windows\System32. The user does not
:: normally have permission to modify files in that directory, which can cause
:: problems because the Selenium Firefox web driver tries to write to
:: geckodriver.log in the current working directory. Moving into the tech Git
:: repo should avoid permission issues.
::
:: You need to pass the /D flag because the MCR computer uses the D:/ drive.
CD /D %~dp0

:: Start the command without a terminal window
start pythonw generate_slides.pyw
