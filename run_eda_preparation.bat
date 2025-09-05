@echo off
echo Starting EDA Data Preparation...
echo ================================
echo.
echo This will:
echo 1. Scan D:\OLD OLD Backups\Music\ALL MUSIC
echo 2. Extract metadata and find duplicates
echo 3. Migrate unique files to F:\data_test
echo.
echo Press Ctrl+C to cancel or any key to continue...
pause > nul

uv run python prepare_eda_data.py "D:\OLD OLD Backups\Music\ALL MUSIC" "F:\data_test"

echo.
echo ================================
echo Data preparation complete!
echo Now run the Jupyter notebook for analysis:
echo   uv run jupyter notebook audio_classification_eda.ipynb
echo.
pause