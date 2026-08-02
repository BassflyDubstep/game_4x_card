@echo off
setlocal enabledelayedexpansion

:: --- CONFIGURATION ---
set BUILD_DIR=build
set BUILD_TYPE=Debug
:: Change "Ninja" to "Visual Studio 17 2022" or "MinGW Makefiles" if needed
set GENERATOR="Visual Studio 17 2022" 

echo =========================================
echo  Starting Clean CMake Build
echo =========================================

:: 1. Clean previous build artifact directories
if exist %BUILD_DIR% (
    echo Removing existing build directory...
    rmdir /s /q %BUILD_DIR%
)

:: 2. Configure the project
echo Configuring project with CMake...
cmake -S . -B %BUILD_DIR% -G %GENERATOR% -DCMAKE_BUILD_TYPE=%BUILD_TYPE%
if %ERRORLEVEL% neq 0 (
    echo [ERROR] CMake configuration failed!
    goto error
)

:: 3. Build the project
echo Building project...
cmake --build %BUILD_DIR% --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build compilation failed!
    goto error
)

echo =========================================
echo  Build Completed Successfully^^!
echo =========================================
pause
exit /b 0

:error
echo Build execution terminated due to errors.
pause
exit /b 1