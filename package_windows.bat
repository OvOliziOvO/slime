@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist slimecore.dll (
  echo [ERROR] Missing slimecore.dll. Run build_cpu_x64.bat first.
  exit /b 1
)
if not exist release\rtx30_40\slimecore_gpu.dll (
  echo [ERROR] Missing RTX 30/40 GPU DLL. Run build_gpu_x64.bat first.
  exit /b 1
)

set "NATIVE_ARGS=--add-binary=slimecore.dll;. --add-binary=release\rtx30_40\slimecore_gpu.dll;. --add-data=color_card;."

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SlimeFinder_RTX30_40 %NATIVE_ARGS% SlimeFinder.py
if errorlevel 1 exit /b 1

echo Built dist\SlimeFinder_RTX30_40.exe.
