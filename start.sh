#!/bin/bash

echo "🚀 Starting AI Trading Co-Pilot..."

# Function to handle cleanup
cleanup() {
    echo "🛑 Stopping AI Trading Co-Pilot..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if required files exist
if [ ! -f "backend/app.py" ]; then
    echo "❌ Backend not found. Please run ./setup.sh first"
    exit 1
fi

if [ ! -f "package.json" ]; then
    echo "❌ Frontend not found. Please run ./setup.sh first"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ Environment file not found. Please check your .env configuration"
    exit 1
fi

echo "✅ All files found"

# Start backend
echo "🔧 Starting backend server..."
cd backend
python3 app.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend development server..."
npm start &
FRONTEND_PID=$!

echo "🎉 AI Trading Co-Pilot is starting up!"
echo ""
echo "📊 Dashboard will open at: http://localhost:3000"
echo "🔌 Backend API running at: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID