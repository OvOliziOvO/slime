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
  exit /b 1
)

set "NVCC="
if defined CUDA_PATH if exist "%CUDA_PATH%\bin\nvcc.exe" set "NVCC=%CUDA_PATH%\bin\nvcc.exe"
if not defined NVCC (
  for /f "delims=" %%i in ('where nvcc 2^>nul') do if not defined NVCC set "NVCC=%%i"
)
if not defined NVCC (
  echo [ERROR] Cannot find nvcc. Set CUDA_PATH first.
  exit /b 1
)

call "%VSINSTALL%\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64
if errorlevel 1 exit /b 1

set "OUTDIR=%~dp0release\rtx30_40"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if errorlevel 1 exit /b 1

if exist "%OUTDIR%\slimecore_gpu.dll" del /f /q "%OUTDIR%\slimecore_gpu.dll"
if exist "%OUTDIR%\slimecore_gpu.lib" del /f /q "%OUTDIR%\slimecore_gpu.lib"
if exist "%OUTDIR%\slimecore_gpu.exp" del /f /q "%OUTDIR%\slimecore_gpu.exp"

"%NVCC%" -O3 -Xptxas=-v --shared -allow-unsupported-compiler ^
  -gencode arch=compute_86,code=sm_86 ^
  -gencode arch=compute_89,code=sm_89 ^
  -gencode arch=compute_89,code=compute_89 ^
  -o "%OUTDIR%\slimecore_gpu.dll" SlimeCoreGPU.cu
if errorlevel 1 exit /b 1
echo Built release\rtx30_40\slimecore_gpu.dll for RTX 30/40 series.
