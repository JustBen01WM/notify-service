# Creates a "WM Notifier" shortcut on the Desktop (and one in this folder).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $here "venv\Scripts\pythonw.exe"
$icon = Join-Path $here "assets\wm-notifier.ico"
if (-not (Test-Path $pythonw)) { Write-Host "Run setup.bat first."; exit 1 }

$shell = New-Object -ComObject WScript.Shell
$targets = @([Environment]::GetFolderPath("Desktop"), $here)
foreach ($dir in $targets) {
    $lnk = $shell.CreateShortcut((Join-Path $dir "WM Notifier.lnk"))
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = "`"$(Join-Path $here 'launcher.py')`""
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation = $icon
    $lnk.Description = "WM Notifier"
    $lnk.Save()
}
Write-Host "Shortcut created on your Desktop."
