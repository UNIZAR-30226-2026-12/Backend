@echo off
echo Installing Python dependencies...
cd backend
pip install -r requirements.txt
cd ..

echo Installing Node.js dependencies...
cd frontend
call npm install
cd ..

echo Starting Backend...
start "Reversi Backend" cmd /k "cd backend && python -m uvicorn backend:app --reload --port 8081"

echo Starting Frontend...
start "Reversi Frontend" cmd /k "cd frontend && npm run dev -- --port 8080"

echo Done! Servers should be running in new windows.
pause
