@echo off
rem CoH Workshop launcher.
rem
rem Runs the workshop HTTP server using Blender's bundled Python, then
rem opens a browser. Closing this window shuts the workshop down.

setlocal

if defined BLENDER (
    set "BLENDER_EXE=%BLENDER%"
) else if exist "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
) else if exist "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
) else if exist "C:\Program Files\Blender Foundation\Blender 4.1\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"
) else if exist "C:\Program Files\Blender Foundation\Blender 4.0\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"
) else (
    where blender >nul 2>&1
    if errorlevel 1 (
        echo Could not locate blender.exe. Set BLENDER env var to its full path,
        echo or install Blender 4.0+ to the default location.
        pause
        exit /b 2
    )
    set "BLENDER_EXE=blender"
)

echo Starting CoH Workshop... (close this window to stop)
"%BLENDER_EXE%" --background --python "%~dp0workshop\server.py"
