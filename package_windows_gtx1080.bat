@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist slimecore.dll (
  echo [ERROR] Missing slimecore.dll. Run build_cpu_x64.bat first.
  exit /b 1
)
if not exist release\gtx1080\slimecore_gpu.dll (
  echo [ERROR] Missing GTX 1080 GPU DLL. Run build_gpu_gtx1080_x64.bat first.
  exit /b 1
)

set "NATIVE_ARGS=--add-binary=slimecore.dll;. --add-binary=release\gtx1080\slimecore_gpu.dll;. --add-data=color_card;."
if exist cubiomes.dll set "NATIVE_ARGS=%NATIVE_ARGS% --add-binary=cubiomes.dll;."
if exist libwinpthread-1.dll set "NATIVE_ARGS=%NATIVE_ARGS% --add-binary=libwinpthread-1.dll;."

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SlimeFinder_GTX1080 %NATIVE_ARGS% SlimeFinder.py
if errorlevel 1 exit /b 1

echo Built dist\SlimeFinder_GTX1080.exe.
