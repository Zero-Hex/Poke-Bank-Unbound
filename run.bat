@echo off
echo Starting UnboundBank...
echo.
pip install flask >nul 2>&1
python app.py
pause
