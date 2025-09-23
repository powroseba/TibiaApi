# Crystal Server Proxy

The proxy has been organized in the `proxy/` directory.

## Quick Commands

```bash
# Start proxy (from crystalserver root)
./start_proxy.sh

# Or go to proxy directory
cd proxy/
./simple_proxy.py

# Test the proxy
cd proxy/
./simple_test.py
```

## Directory Structure

```
crystalserver/
├── start_proxy.sh          # Quick launcher
└── proxy/                  # Proxy files
    ├── README.md           # Quick start guide
    ├── simple_proxy.py     # Main proxy (recommended)
    ├── crystal_proxy.py    # Advanced proxy  
    ├── simple_test.py      # Basic tests
    ├── test_proxy.py       # Advanced tests
    ├── setup_proxy.sh      # Setup script
    ├── requirements.txt    # Dependencies
    ├── PROXY_README.md     # Detailed docs
    └── PROXY_SUMMARY.md    # Project overview
```

## What It Does

Routes client connections to appropriate CrystalServer backends:

- **HTTP /login.php** → Port 8090 (character list)
- **TCP Login** → Port 7171 (handshake)
- **TCP Game** → Port 7172 (gameplay)

Client connects to single proxy port (default 7170), proxy auto-detects protocol type.

For full documentation, see `proxy/README.md`.
