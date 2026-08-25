@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
  for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%i"
)

if not defined VSINSTALL (
  echo [ERROR] Cannot find Visual Studio C++ x64 tools.
  echo Install Visual Studio Build Tools and select "Desktop development with C++".
  pause
  exit /b 1
)

call "%VSINSTALL%\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64
if errorlevel 1 exit /b 1

if exist slimecore.dll del /f /q slimecore.dll
if exist slimecore.lib del /f /q slimecore.lib
if exist slimecore.exp del /f /q slimecore.exp
if exist SlimeCore.obj del /f /q SlimeCore.obj
if exist SlimeCore_precise_batch.obj del /f /q SlimeCore_precise_batch.obj

if exist SlimeCore_precise_batch.cpp (
  echo Building CPU DLL from SlimeCore_precise_batch.cpp ...
  cl /nologo /O2 /Ob3 /Oi /Ot /GL /Gw /Gy /arch:AVX2 /std:c++17 /EHsc /MD /openmp /LD SlimeCore_precise_batch.cpp /Fe:slimecore.dll /link /LTCG
) else (
  echo Building CPU DLL from SlimeCore.cpp ...
  cl /nologo /O2 /Ob3 /Oi /Ot /GL /Gw /Gy /arch:AVX2 /std:c++17 /EHsc /MD /openmp /LD SlimeCore.cpp /Fe:slimecore.dll /link /LTCG
)
if errorlevel 1 (
  echo [ERROR] CPU DLL build failed.
  pause
  exit /b 1
)

echo.
echo Built slimecore.dll. Checking machine type...
dumpbin /headers slimecore.dll | findstr /C:"machine (x64)"
dumpbin /exports slimecore.dll | findstr search_slime_clusters
echo.
echo Done. Put slimecore.dll next to the Python program and restart it.
pause
