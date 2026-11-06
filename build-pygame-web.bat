@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  LEGENDARY SURVIVAL - PYGBAG WEBASSEMBLY BUILD SCRIPT
echo =====================================================================
echo [1/4] Checking Python environment...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found on PATH! Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

echo [2/4] Ensuring pygbag is installed...
python -m pip install pygbag --upgrade --quiet

echo [3/4] Staging clean Pygame source files...
if exist "build_pygame_stage" rmdir /s /q "build_pygame_stage"
mkdir "build_pygame_stage"
copy /y "main.py" "build_pygame_stage\main.py" >nul
copy /y "audio_settings.py" "build_pygame_stage\audio_settings.py" >nul

echo [4/4] Building Pygame WebAssembly distribution (pygbag --build --ume_block 0)...
python -m pygbag --build --app_name pygame --ume_block 0 build_pygame_stage

if not exist "build_pygame_stage\build\web\index.html" (
    echo [ERROR] Pygbag build failed! Please check error output above.
    if exist "build_pygame_stage" rmdir /s /q "build_pygame_stage"
    pause
    exit /b 1
)

echo [*] Copying built static WebAssembly assets to legendary-survival-web\frontend\pygame...
if not exist "legendary-survival-web\frontend\pygame" mkdir "legendary-survival-web\frontend\pygame"
xcopy /y /e "build_pygame_stage\build\web\*" "legendary-survival-web\frontend\pygame\" >nul

if exist "build_pygame_stage" rmdir /s /q "build_pygame_stage"

echo =====================================================================
echo  SUCCESS: Pygame WebAssembly build completed!
echo  Assets ready at: legendary-survival-web\frontend\pygame\
echo  Playable directly in Web Hub via iframe: /pygame/index.html
echo =====================================================================

