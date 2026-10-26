@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem BeardedWolf: local copy of existing Windows credentials, WITHOUT decryption.
rem Sensitive backup! NEVER send this folder to chat/GitHub/Syncthing.
set "BASE=%USERPROFILE%\Documents\BeardedWolf-AccessAudit"
set "OUT=%BASE%\PRIVATE-%COMPUTERNAME%-%RANDOM%-%RANDOM%"
mkdir "%OUT%\FileZilla" >nul 2>&1
if errorlevel 1 (echo Could not create export directory.& exit /b 1)
icacls "%OUT%" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" /grant:r "*S-1-5-18:(OI)(CI)F" /grant:r "*S-1-5-32-544:(OI)(CI)F" >nul
if errorlevel 1 (echo Could not protect the export directory ACL. Stopping.& exit /b 1)
if exist "%APPDATA%\FileZilla\sitemanager.xml" copy /y "%APPDATA%\FileZilla\sitemanager.xml" "%OUT%\FileZilla\" >nul
if exist "%APPDATA%\FileZilla\recentservers.xml" copy /y "%APPDATA%\FileZilla\recentservers.xml" "%OUT%\FileZilla\" >nul
if exist "%APPDATA%\FileZilla\filezilla.xml" copy /y "%APPDATA%\FileZilla\filezilla.xml" "%OUT%\FileZilla\" >nul
if exist "%USERPROFILE%\.ssh\" robocopy "%USERPROFILE%\.ssh" "%OUT%\Windows-OpenSSH" /E /XJ /SL /SJ /R:0 /W:0 /COPY:DAT >nul
if exist "%APPDATA%\WinSCP.ini" copy /y "%APPDATA%\WinSCP.ini" "%OUT%\" >nul
reg query "HKCU\Software\SimonTatham\PuTTY" >nul 2>&1
if not errorlevel 1 reg export "HKCU\Software\SimonTatham\PuTTY" "%OUT%\PuTTY.reg" /y >nul
reg query "HKCU\Software\Martin Prikryl\WinSCP 2" >nul 2>&1
if not errorlevel 1 reg export "HKCU\Software\Martin Prikryl\WinSCP 2" "%OUT%\WinSCP.reg" /y >nul
echo.
echo EXPORT FINISHED: "%OUT%"
echo Includes saved credentials and private SSH keys (if available).
echo Files NOT encrypted. Keep local or move to BitLocker media.
echo NEVER upload or sync this private directory.
echo.
endlocal
