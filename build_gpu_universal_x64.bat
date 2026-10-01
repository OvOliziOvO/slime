@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "NVCC=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin\nvcc.exe"
if not exist "%NVCC%" exit /b 1

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" set "VSWHERE=C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" exit /b 1
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%i"
if not defined VSINSTALL if exist "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" set "VSINSTALL=C:\Program Files\Microsoft Visual Studio\18\Community"
if not defined VSINSTALL exit /b 1

call "%VSINSTALL%\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64
if errorlevel 1 exit /b 1

set "OUTDIR=%~dp0release\universal"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

"%NVCC%" -O3 -std=c++17 -Xcompiler=/MD -Xptxas=-v --shared -allow-unsupported-compiler ^
  -gencode arch=compute_61,code=sm_61 ^
  -gencode arch=compute_61,code=compute_61 ^
  -gencode arch=compute_75,code=sm_75 ^
  -gencode arch=compute_86,code=sm_86 ^
  -gencode arch=compute_89,code=sm_89 ^
  -gencode arch=compute_120,code=sm_120 ^
  -gencode arch=compute_120,code=compute_120 ^
  -o "%OUTDIR%\slimecore_gpu.dll" SlimeCoreGPU.cu
if errorlevel 1 exit /b 1

echo Built universal GTX 10 through RTX 50 GPU DLL.
