# Crystal Server Proxy

A Python proxy server for CrystalServer that intelligently routes multiple protocols on a single port.

## Quick Start

```bash
# Setup and install dependencies
./setup_proxy.sh

# Start the proxy
./simple_proxy.py --proxy-port 7170

# Test the proxy
./simple_test.py
```

## What's Included

- **`simple_proxy.py`** ⭐ - Main proxy implementation (recommended)
- **`crystal_proxy.py`** - Advanced proxy with additional features
- **`test_proxy.py`** - Comprehensive test suite (requires aiohttp)
- **`simple_test.py`** - Basic test script (no dependencies)
- **`setup_proxy.sh`** - Automated setup script
- **`requirements.txt`** - Python dependencies

## Documentation

- **`PROXY_README.md`** - Detailed documentation and usage guide
- **`PROXY_SUMMARY.md`** - Project overview and architecture

## Architecture

The proxy handles three types of traffic:

```
[Game Client] → [Proxy:7170] → Routes to:
                                ├─ HTTP /login.php → Backend:8090
                                ├─ TCP Login → Backend:7171
                                └─ TCP Game → Backend:7172
```

## Features

✅ **Single Port** - Clients connect to one port only
✅ **Auto Detection** - Automatically detects protocol type  
✅ **HTTP Support** - Handles login.php requests
✅ **TCP Proxying** - Bidirectional data forwarding
✅ **Robust Logging** - Detailed connection tracking
✅ **Easy Setup** - One-command installation

## Usage

Point your game client to the proxy:
- **Host**: `localhost` (or server IP)
- **Port**: `7170` (or custom proxy port)

The proxy automatically routes traffic to the appropriate CrystalServer backend ports.

## License

GPL-3.0 (same as CrystalServer)
