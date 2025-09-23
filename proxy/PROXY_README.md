# Crystal Server Proxy

A Python proxy server for the CrystalServer game that handles multiple protocols on a single port.

## Overview

This proxy acts as an intermediary between game clients and the CrystalServer, routing different types of traffic:

1. **HTTP POST `/login.php`** → Backend HTTP server (default: `127.0.0.1:8090`)
2. **TCP Login Handshake** → Login protocol server (default: `127.0.0.1:7171`)  
3. **TCP Game Session** → Game protocol server (default: `127.0.0.1:7172`)

## Features

- **Single Port**: Clients connect to one port, proxy detects protocol type
- **HTTP Support**: Handles POST requests to `/login.php` 
- **TCP Protocol Detection**: Automatically detects login vs game protocols
- **Bidirectional Proxying**: Full duplex data forwarding
- **Logging**: Detailed logging of connections and data transfer
- **Graceful Shutdown**: Properly closes all connections on exit

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the proxy:**
```bash
python simple_proxy.py --proxy-port 7170
```

3. **Configure your game client to connect to:**
   - Host: `localhost` (or your server IP)
   - Port: `7170` (or whatever you set as proxy-port)

## Usage

### Basic Usage
```bash
# Start proxy on port 7170 (default)
python simple_proxy.py

# Start on custom port
python simple_proxy.py --proxy-port 8000

# Enable verbose logging
python simple_proxy.py --verbose
```

### Advanced Configuration
```bash
python simple_proxy.py \\
    --proxy-port 7170 \\
    --login-host 192.168.1.100 \\
    --login-port 7171 \\
    --game-host 192.168.1.100 \\
    --game-port 7172 \\
    --http-host 192.168.1.100 \\
    --http-port 8090 \\
    --verbose
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--proxy-port` | 7170 | Port for proxy to listen on |
| `--login-host` | 127.0.0.1 | Backend login server host |
| `--login-port` | 7171 | Backend login server port |
| `--game-host` | 127.0.0.1 | Backend game server host |
| `--game-port` | 7172 | Backend game server port |
| `--http-host` | 127.0.0.1 | Backend HTTP server host |
| `--http-port` | 8090 | Backend HTTP server port |
| `--verbose` | False | Enable verbose logging |

## Protocol Detection

The proxy automatically detects the protocol type:

### HTTP Detection
- Looks for HTTP methods: `GET`, `POST`, `PUT`, etc.
- Routes `/login.php` POST requests to HTTP backend
- Returns 404 for other HTTP requests

### TCP Game Protocol Detection  
- Analyzes packet structure and size
- **Login Protocol**: Smaller packets (< 150 bytes) → port 7171
- **Game Protocol**: Larger packets (≥ 150 bytes) → port 7172

## Architecture

```
[Game Client] 
    ↓ (connects to proxy_port)
[Crystal Proxy]
    ↓ (routes based on protocol)
    ├─ HTTP /login.php → [HTTP Backend :8090]
    ├─ TCP Login → [Login Server :7171] 
    └─ TCP Game → [Game Server :7172]
```

## Logging

The proxy provides detailed logging:

```
2025-01-XX 10:30:15,123 - INFO - 🎮 Crystal Server Proxy started on port 7170
2025-01-XX 10:30:16,456 - INFO - 🔗 New connection from ('127.0.0.1', 52341)
2025-01-XX 10:30:16,457 - INFO - 🌐 HTTP request from ('127.0.0.1', 52341)
2025-01-XX 10:30:16,458 - INFO - 📨 POST /login.php
2025-01-XX 10:30:16,459 - INFO - 🔄 Forwarding login request to backend...
2025-01-XX 10:30:16,523 - INFO - ✅ Login request forwarded successfully
```

## Files

- **`simple_proxy.py`** - Main proxy implementation (recommended)
- **`crystal_proxy.py`** - Advanced proxy with additional features
- **`requirements.txt`** - Python dependencies
- **`README.md`** - This documentation

## Error Handling

The proxy handles various error conditions:

- **Connection timeouts**: 5-second timeout for initial data
- **Backend unavailable**: Sends appropriate HTTP error responses
- **Protocol errors**: Logs errors and closes connections gracefully
- **Keyboard interrupt**: Graceful shutdown of all connections

## Development

### Running with Debug Mode
```bash
python simple_proxy.py --verbose
```

### Testing HTTP Endpoint
```bash
curl -X POST http://localhost:7170/login.php \\
     -H "Content-Type: application/x-www-form-urlencoded" \\
     -d "username=test&password=test"
```

### Testing TCP Connection
```bash
# Using telnet (will be detected as game protocol)
telnet localhost 7170
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```
   OSError: [Errno 48] Address already in use
   ```
   - Change the proxy port: `--proxy-port 7171`
   - Check what's using the port: `lsof -i :7170`

2. **Backend connection refused**
   ```
   ConnectionRefusedError: [Errno 61] Connection refused
   ```
   - Ensure CrystalServer is running
   - Check backend host/port configuration
   - Verify firewall settings

3. **Protocol detection issues**
   - Enable verbose logging to see detection details
   - Check packet sizes and content in logs
   - Adjust detection thresholds if needed

### Performance Considerations

- The proxy is designed for typical game server loads
- Each connection uses minimal resources
- Async I/O provides good concurrency
- Monitor memory usage for high connection counts

## Security Notes

- This proxy does not implement authentication
- It forwards all traffic transparently
- Use appropriate firewall rules
- Consider TLS termination if needed

## License

This proxy is designed to work with CrystalServer and follows the same GPL license.
