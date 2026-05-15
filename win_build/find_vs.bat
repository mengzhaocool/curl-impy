@echo off
setlocal enabledelayedexpansion
::: find_vs.bat - Find Visual Studio installation path (replaces vswhere)
::: Usage: call find_vs.bat [min_version] [max_version]
:::   min_version: minimum VS major version (default: 16)
:::   max_version: maximum VS major version, exclusive (default: 99)
::: Outputs: the VS installation path to stdout (first match)
::: Exit code: 0=found, 1=not found

set "FV_MIN=16"
set "FV_MAX=99"
if not "%~1"=="" set "FV_MIN=%~1"
if not "%~2"=="" set "FV_MAX=%~2"

::: Priority 1: Scan _Instances state.json (same data source as vswhere)
set "FV_FOUND="
set "FV_CACHE=C:\ProgramData\Microsoft\VisualStudio\Packages"
if not exist "%FV_CACHE%\_Instances" (
    set "FV_CACHE=%LOCALAPPDATA%\Microsoft\VisualStudio\Packages"
)
if exist "%FV_CACHE%\_Instances" (
    for /f "delims=" %%d in ('dir /b /ad "%FV_CACHE%\_Instances" 2^>nul') do (
        if not defined FV_FOUND (
            set "FV_STATE=%FV_CACHE%\_Instances\%%d\state.json"
            if exist "!FV_STATE!" (
                for /f "tokens=1,* delims=:" %%a in ('findstr /C:"\"installationPath\"" "!FV_STATE!" 2^>nul') do (
                    set "FV_RAW=%%b"
                )
                ::: Strip quotes and whitespace from value
                set "FV_PATH=!FV_RAW: =!"
                set "FV_PATH=!FV_PATH:"=!"
                set "FV_PATH=!FV_PATH:\\=\!"
                for /f "tokens=1,* delims=:" %%a in ('findstr /C:"\"installationVersion\"" "!FV_STATE!" 2^>nul') do (
                    set "FV_VRAW=%%b"
                )
                set "FV_VER=!FV_VRAW: =!"
                set "FV_VER=!FV_VER:"=!"
                for /f "tokens=1 delims=." %%m in ("!FV_VER!") do set "FV_MAJOR=%%m"
                if "!FV_MAJOR!"=="2022" set "FV_MAJOR=17"
                if "!FV_MAJOR!"=="2019" set "FV_MAJOR=16"
                if "!FV_MAJOR!"=="2017" set "FV_MAJOR=15"
                if !FV_MAJOR! GEQ !FV_MIN! if !FV_MAJOR! LSS !FV_MAX! (
                    if exist "!FV_PATH!\VC\Auxiliary\Build\vcvarsall.bat" (
                        set "FV_FOUND=!FV_PATH!"
                    )
                )
            )
        )
    )
)
if defined FV_FOUND echo !FV_FOUND!& endlocal & exit /b 0

::: Priority 2: Probe well-known directories
for %%e in (Enterprise Professional Community) do (
    for %%d in ("C:\Program Files\Microsoft Visual Studio" "D:\Program Files\Microsoft Visual Studio" "C:\Program Files (x86)\Microsoft Visual Studio" "D:\Program Files (x86)\Microsoft Visual Studio") do (
        for %%v in (2022 2019) do (
            if not defined FV_FOUND (
                set "FV_PROBE=%%~d\%%v\%%e"
                if exist "!FV_PROBE!\VC\Auxiliary\Build\vcvarsall.bat" (
                    if "%%v"=="2022" set "FV_MAJOR=17"
                    if "%%v"=="2019" set "FV_MAJOR=16"
                    if !FV_MAJOR! GEQ !FV_MIN! if !FV_MAJOR! LSS !FV_MAX! (
                        set "FV_FOUND=!FV_PROBE!"
                    )
                )
            )
        )
    )
)
if defined FV_FOUND echo !FV_FOUND!& endlocal & exit /b 0

endlocal & exit /b 1
