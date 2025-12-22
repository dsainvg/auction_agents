@echo off
echo Starting IPL Mock Auction Dashboard with logging (UTF-8 enabled)...
rem Ensure misc folder exists
if not exist misc mkdir misc

rem Set console to UTF-8 code page to avoid UnicodeEncodeError on Windows
chcp 65001 >nul

rem Force Python to use UTF-8 mode and set stdout/stderr encoding
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem Launch streamlit and capture both stdout and stderr to log
streamlit run streamlit_dashboard.py --server.port 8501 --server.address localhost > misc\out.log 2>&1