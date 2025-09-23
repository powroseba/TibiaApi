#!/bin/bash
# Quick launcher for Crystal Server Proxy

echo "🎮 Starting Crystal Server Proxy..."
echo "📁 Proxy location: $(pwd)/proxy"
echo ""

# Check if proxy directory exists
if [ ! -d "proxy" ]; then
    echo "❌ Proxy directory not found!"
    echo "💡 Make sure you're in the crystalserver root directory"
    exit 1
fi

# Change to proxy directory and run
cd proxy

# Check if setup has been run
if [ ! -x "simple_proxy.py" ]; then
    echo "🔧 Setting up proxy for first time..."
    ./setup_proxy.sh
    echo ""
fi

# Start the proxy with default settings
echo "🚀 Launching proxy on port 7170..."
echo "🛑 Press Ctrl+C to stop"
echo ""

./simple_proxy.py "$@"
