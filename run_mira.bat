@echo off
echo Starting Mira Backend...
start /b uvicorn backend.main:app --host 127.0.0.1 --port 8000

echo Starting Mira UI...
cd frontend
npm start
