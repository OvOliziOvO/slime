@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem GTX 10 series (Pascal) requires CUDA 12.x. CUDA 13 removed sm_61.
set "NVCC=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin\nvcc.exe"
if not exist "%NVCC%" (
  echo [ERROR] CUDA 12.9 nvcc was not found:
  echo         %NVCC%
  echo Install the CUDA 12.9 nvcc and cudart components first.
  exit /b 1
)

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
  for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%i"
)
if not defined VSINSTALL (
  echo [ERROR] Cannot find Visual Studio C++ x64 tools.
  exit /b 1
)

call "%VSINSTALL%\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64
if errorlevel 1 exit /b 1

set "OUTDIR=%~dp0release\gtx1080"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
if errorlevel 1 exit /b 1

if exist "%OUTDIR%\slimecore_gpu.dll" del /f /q "%OUTDIR%\slimecore_gpu.dll"
if exist "%OUTDIR%\slimecore_gpu.lib" del /f /q "%OUTDIR%\slimecore_gpu.lib"
if exist "%OUTDIR%\slimecore_gpu.exp" del /f /q "%OUTDIR%\slimecore_gpu.exp"

"%NVCC%" -O3 -Xptxas=-v --shared -allow-unsupported-compiler ^
  -gencode arch=compute_61,code=sm_61 ^
  -gencode arch=compute_61,code=compute_61 ^
  -o "%OUTDIR%\slimecore_gpu.dll" SlimeCoreGPU.cu
if errorlevel 1 exit /b 1

echo Built release\gtx1080\slimecore_gpu.dll for GTX 10 series ^(sm_61 + compute_61 PTX^).
