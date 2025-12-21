@echo off
echo Starting IPL Mock Auction Dashboard with logging...
if not exist misc mkdir misc
streamlit run streamlit_dashboard.py --server.port 8501 --server.address localhost > misc\out.log 2>&1