#!/bin/bash
# Setup script for Crystal Server Proxy

echo "🎮 Crystal Server Proxy Setup"
echo "============================="
echo "📁 Working in proxy directory: $(pwd)"

# Check Python version
echo "🐍 Checking Python version..."
python3 --version

# Check if pip is available
echo "📦 Checking pip..."
python3 -m pip --version

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📋 Installing Python dependencies..."
    python3 -m pip install -r requirements.txt
else
    echo "⚠️  No requirements.txt found, installing minimal dependencies..."
    python3 -m pip install aiohttp
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x simple_proxy.py
chmod +x simple_test.py
chmod +x crystal_proxy.py 2>/dev/null || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 To start the proxy:"
echo "   ./simple_proxy.py --proxy-port 7170"
echo ""
echo "🧪 To test the proxy:"
echo "   ./simple_test.py"
echo ""
echo "📖 Documentation:"
echo "   - README.md - Quick start guide"
echo "   - PROXY_README.md - Detailed documentation"  
echo "   - PROXY_SUMMARY.md - Project overview"
