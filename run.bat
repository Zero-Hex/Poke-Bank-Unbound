@echo off
echo Starting UnboundBank...
echo.
pip install -r requirements.txt >nul 2>&1
python app.py
pause
