@echo off
REM Batch script to build the tradelogger.py application into a standalone executable.

echo [INFO] Setting up the build environment...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create a virtual environment. Make sure Python is installed and in your PATH.
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate

echo [INFO] Installing necessary packages...
pip install pyinstaller ibapi tradingview_ta
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install required packages. Check your internet connection.
    pause
    exit /b 1
)

echo [INFO] Building the executable with PyInstaller...
pyinstaller --name "TradeLogger" --onefile --windowed --clean tradelogger.py
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller failed to build the executable.
    pause
    exit /b 1
)

echo [SUCCESS] Build complete.
echo The executable 'TradeLogger.exe' can be found in the 'dist' folder.

pause
