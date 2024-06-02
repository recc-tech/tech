# https://stackoverflow.com/a/9701907
function New-Shortcut {
	param ($LinkPath, $TargetPath)

	$WshShell = New-Object -comObject WScript.Shell
	$Shortcut = $WshShell.CreateShortcut($LinkPath)
	$Shortcut.TargetPath = $TargetPath
	$Shortcut.Save()
}

$Desktop = "D:\Users\Tech\Desktop"
$ScriptsDir = "D:\Users\Tech\Documents\tech\scripts"

New-Shortcut -LinkPath "$Desktop\Update Scripts.lnk"    -TargetPath "$ScriptsDir\update_scripts.bat"
New-Shortcut -LinkPath "$Desktop\Undo Updates.lnk"      -TargetPath "$ScriptsDir\undo_updates.bat"
New-Shortcut -LinkPath "$Desktop\Check Credentials.lnk" -TargetPath "$ScriptsDir\check_credentials.bat"
New-Shortcut -LinkPath "$Desktop\Download Assets.lnk"   -TargetPath "$ScriptsDir\download_pco_assets.bat"
New-Shortcut -LinkPath "$Desktop\Generate Slides.lnk"   -TargetPath "$ScriptsDir\generate_slides.bat"
New-Shortcut -LinkPath "$Desktop\MCR Setup.lnk"         -TargetPath "$ScriptsDir\mcr_setup.bat"
New-Shortcut -LinkPath "$Desktop\MCR Teardown.lnk"      -TargetPath "$ScriptsDir\mcr_teardown.bat"
