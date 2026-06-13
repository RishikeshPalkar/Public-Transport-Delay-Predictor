@echo off
:: Navigate to the project directory
cd /d "%~dp0"

:: Execute the python ingestion script using the virtual environment interpreter
echo Running SBB Ingestion Pipeline...
.venv\Scripts\python src\data_pipeline\ingest.py

echo Pipeline execution finished at %date% %time%
pause
