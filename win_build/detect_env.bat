@echo off
::: detect_env.bat - Detect build tools and set up MSVC environment
::: Usage: call detect_env.bat [arch] [vs_version]
::: Sets: CMAKE_EXE, NINJA_EXE, GO_EXE, PERL_EXE, PYTHON_EXE, NASM_EXE, GIT_EXE
:::       VCVARSALL, VS_PATH, WIN10_SDK_PATH, WIN10_SDK_VERSION, ARCH

::: Parse arguments
if not "%~1"=="" set "ARCH=%~1"
if not "%~2"=="" set "VS_VERSION=%~2"
if not defined ARCH set ARCH=x64
if not defined VS_VERSION set VS_VERSION=2019

echo [detect_env] Detecting build environment ...

::: ---- Find Visual Studio via find_vs.bat (replaces vswhere.exe) ----
set "VS_PATH="
set "VS_MAJOR=17"
if "%VS_VERSION%"=="2022" set "VS_MAJOR=17"
if "%VS_VERSION%"=="2019" set "VS_MAJOR=16"
if "%VS_VERSION%"=="2017" set "VS_MAJOR=15"
for /f "delims=" %%p in ('call "%~dp0find_vs.bat" %VS_MAJOR%') do set "VS_PATH=%%p"
if not defined VS_PATH echo [ERROR] VS not found & exit /b 1
echo [detect_env] VS Path: %VS_PATH%

::: ---- Find vcvarsall.bat ----
set "VCVARSALL=%VS_PATH%\VC\Auxiliary\Build\vcvarsall.bat"
if exist "%VCVARSALL%" goto :vcvarsall_ok
echo [ERROR] vcvarsall.bat not found
exit /b 1
:vcvarsall_ok

::: ---- Call vcvarsall.bat ----
echo [detect_env] Setting up MSVC environment...
call "%VCVARSALL%" %ARCH%
if %ERRORLEVEL% neq 0 echo [ERROR] vcvarsall.bat failed & exit /b 1

::: ---- Find CMake ----
set "CMAKE_EXE="
where cmake >nul 2>&1 && set "CMAKE_EXE=cmake"
if defined CMAKE_EXE goto :cmake_found
if exist "C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe" set "CMAKE_EXE=C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe"
if defined CMAKE_EXE goto :cmake_found
if exist "C:\msys64\mingw64\bin\cmake.exe" set "CMAKE_EXE=C:\msys64\mingw64\bin\cmake.exe"
if defined CMAKE_EXE goto :cmake_found
echo [ERROR] CMake not found & exit /b 1
:cmake_found
echo [detect_env] CMake: %CMAKE_EXE%

::: ---- Find Ninja ----
set "NINJA_EXE="
where ninja >nul 2>&1 && set "NINJA_EXE=ninja"
if defined NINJA_EXE goto :ninja_found
if exist "C:\vcpkg\downloads\tools\ninja-1.13.2-windows\ninja.exe" set "NINJA_EXE=C:\vcpkg\downloads\tools\ninja-1.13.2-windows\ninja.exe"
if defined NINJA_EXE goto :ninja_found
if exist "C:\msys64\mingw64\bin\ninja.exe" set "NINJA_EXE=C:\msys64\mingw64\bin\ninja.exe"
if defined NINJA_EXE goto :ninja_found
echo [ERROR] Ninja not found & exit /b 1
:ninja_found
echo [detect_env] Ninja: %NINJA_EXE%

::: ---- Find Go ----
set "GO_EXE="
where go >nul 2>&1 && set "GO_EXE=go"
if defined GO_EXE goto :go_found
if exist "C:\Program Files\Go\bin\go.exe" set "GO_EXE=C:\Program Files\Go\bin\go.exe"
:go_found
if defined GO_EXE echo [detect_env] Go: %GO_EXE%
if not defined GO_EXE echo [WARN] Go not found

::: ---- Find Perl ----
set "PERL_EXE="
where perl >nul 2>&1 && set "PERL_EXE=perl"
if defined PERL_EXE goto :perl_found
if exist "C:\Program Files\Git\usr\bin\perl.exe" set "PERL_EXE=C:\Program Files\Git\usr\bin\perl.exe"
:perl_found
if defined PERL_EXE echo [detect_env] Perl: %PERL_EXE%
if not defined PERL_EXE echo [WARN] Perl not found

::: ---- Find Python ----
set "PYTHON_EXE="
where python >nul 2>&1 && set "PYTHON_EXE=python"
if defined PYTHON_EXE goto :python_found
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe" set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
:python_found
if defined PYTHON_EXE echo [detect_env] Python: %PYTHON_EXE%

::: ---- Find NASM ----
set "NASM_EXE="
where nasm >nul 2>&1 && set "NASM_EXE=nasm"
if defined NASM_EXE goto :nasm_found
if exist "C:\vcpkg\downloads\tools\nasm\nasm-3.01\nasm.exe" set "NASM_EXE=C:\vcpkg\downloads\tools\nasm\nasm-3.01\nasm.exe"
:nasm_found
if defined NASM_EXE echo [detect_env] NASM: %NASM_EXE%

::: ---- Find Git ----
set "GIT_EXE="
where git >nul 2>&1 && set "GIT_EXE=git"
if defined GIT_EXE goto :git_found
if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
:git_found
if not defined GIT_EXE echo [ERROR] Git not found & exit /b 1
echo [detect_env] Git: %GIT_EXE%

::: ---- Find Windows 10 SDK ----
set "WIN10_SDK_PATH="
set "WIN10_SDK_VERSION="
for /f "usebackq tokens=1,2 delims=|" %%a in (`powershell -NoProfile -Command "foreach ($p in @('D:\Program Files (x86)\Windows Kits\10','C:\Program Files (x86)\Windows Kits\10') ) { if (Test-Path $p) { $v = Get-ChildItem (Join-Path $p Include) -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^10\.0\.' } | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name; if ($v) { Write-Output ($p + '|' + $v); break } } }"`) do (
    set "WIN10_SDK_PATH=%%a"
    set "WIN10_SDK_VERSION=%%b"
)
if defined WIN10_SDK_VERSION goto :sdk_found
echo [ERROR] Windows 10 SDK not found
exit /b 1
:sdk_found
echo [detect_env] Windows 10 SDK: %WIN10_SDK_VERSION%

::: ---- Verify cl.exe ----
where cl >nul 2>&1
if %ERRORLEVEL% neq 0 echo [ERROR] cl.exe not found & exit /b 1

echo [detect_env] Environment setup complete.
exit /b 0
