#!/usr/bin/env python3
"""
Crystal Server Proxy
A proxy server that handles HTTP login requests and TCP game protocols
for the CrystalServer game server.

The proxy listens on a single port and routes traffic to:
- HTTP POST /login.php -> 0.0.0.0:8090
- TCP Login handshake -> 0.0.0.0:7171  
- TCP Game session -> 0.0.0.0:7172
"""

import asyncio
import aiohttp
import logging
import struct
import time
from aiohttp import web
from typing import Optional, Tuple
import sys
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CrystalProxy:
    def __init__(self, proxy_port: int = 7170, 
                 login_host: str = "0.0.0.0", login_port: int = 7171,
                 game_host: str = "0.0.0.0", game_port: int = 7172,
                 http_host: str = "0.0.0.0", http_port: int = 8090):
        self.proxy_port = proxy_port
        self.login_host = login_host
        self.login_port = login_port
        self.game_host = game_host
        self.game_port = game_port
        self.http_host = http_host
        self.http_port = http_port
        
        # Server instances
        self.tcp_server = None
        self.http_server = None
        self.app = None
        self.runner = None
        
        # Connection tracking
        self.active_connections = set()
        
    async def start(self):
        """Start both HTTP and TCP servers"""
        try:
            # Start HTTP server for login.php
            await self._start_http_server()
            logger.info(f"HTTP server started on port {self.proxy_port}")
            
            # Start TCP server for game protocols
            await self._start_tcp_server()
            logger.info(f"TCP server started on port {self.proxy_port}")
            
            logger.info("Crystal Proxy is running...")
            
        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            await self.stop()
            raise
    
    async def _start_http_server(self):
        """Start HTTP server for handling login.php requests"""
        self.app = web.Application()
        self.app.router.add_post('/login.php', self.handle_http_login)
        self.app.router.add_route('*', '/{path:.*}', self.handle_http_fallback)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, '0.0.0.0', self.proxy_port)
        await site.start()
        
    async def _start_tcp_server(self):
        """Start TCP server for handling game protocols"""
        self.tcp_server = await asyncio.start_server(
            self.handle_tcp_connection,
            '0.0.0.0',
            self.proxy_port + 1  # Use proxy_port + 1 for TCP to avoid conflict
        )
        
    async def handle_http_login(self, request):
        """Handle HTTP POST requests to /login.php"""
        try:
            logger.info("Received HTTP login request")
            
            # Read the request body
            body = await request.read()
            
            # Forward to the actual login server
            async with aiohttp.ClientSession() as session:
                url = f"http://{self.http_host}:{self.http_port}/login.php"
                
                # Copy headers from original request
                headers = dict(request.headers)
                # Remove hop-by-hop headers
                for header in ['host', 'connection', 'upgrade']:
                    headers.pop(header, None)
                
                async with session.post(url, data=body, headers=headers) as response:
                    response_body = await response.read()
                    
                    # Create response with same status and headers
                    resp = web.Response(
                        body=response_body,
                        status=response.status,
                        headers=response.headers
                    )
                    
                    logger.info(f"Forwarded HTTP login request, status: {response.status}")
                    return resp
                    
        except Exception as e:
            logger.error(f"Error handling HTTP login: {e}")
            return web.Response(text="Internal Server Error", status=500)
    
    async def handle_http_fallback(self, request):
        """Handle other HTTP requests"""
        logger.info(f"Received HTTP {request.method} request to {request.path}")
        return web.Response(text="Not Found", status=404)
    
    async def handle_tcp_connection(self, reader, writer):
        """Handle incoming TCP connections and determine protocol type"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"New TCP connection from {client_addr}")
        
        self.active_connections.add(writer)
        
        try:
            # Read first few bytes to determine protocol type
            protocol_type = await self._detect_protocol(reader)
            
            if protocol_type == "login":
                await self._handle_login_protocol(reader, writer)
            elif protocol_type == "game":
                await self._handle_game_protocol(reader, writer)
            else:
                logger.warning(f"Unknown protocol type from {client_addr}")
                
        except Exception as e:
            logger.error(f"Error handling TCP connection from {client_addr}: {e}")
        finally:
            self.active_connections.discard(writer)
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
    
    async def _detect_protocol(self, reader) -> str:
        """
        Detect if this is a login handshake or game session protocol.
        
        In Tibia-like games:
        - Login protocol starts with specific opcodes
        - Game protocol has different packet structure
        
        This is a simplified detection based on typical patterns.
        """
        try:
            # Peek at first few bytes without consuming them
            first_bytes = await reader.read(6)
            if len(first_bytes) < 6:
                return "unknown"
            
            # Reset the reader position (this is a simplified approach)
            # In practice, you might need to buffer this data
            
            # Typical Tibia login packet structure:
            # 2 bytes: packet length
            # 1 byte: opcode (0x01 for login)
            packet_length = struct.unpack('<H', first_bytes[:2])[0]
            
            # Check if this looks like a login packet
            # Login packets are typically smaller and have specific opcodes
            if packet_length < 200 and len(first_bytes) >= 3:
                opcode = first_bytes[2]
                if opcode == 0x01:  # Login opcode
                    return "login"
                elif opcode in [0x0A, 0x14, 0x1E]:  # Common game opcodes
                    return "game"
            
            # Default to game protocol for longer packets
            return "game" if packet_length > 50 else "login"
            
        except Exception as e:
            logger.error(f"Error detecting protocol: {e}")
            return "unknown"
    
    async def _handle_login_protocol(self, client_reader, client_writer):
        """Handle login protocol by proxying to login server"""
        logger.info("Handling login protocol")
        
        try:
            # Connect to login server
            server_reader, server_writer = await asyncio.open_connection(
                self.login_host, self.login_port
            )
            
            # Start bidirectional proxy
            await asyncio.gather(
                self._proxy_data(client_reader, server_writer, "client->login_server"),
                self._proxy_data(server_reader, client_writer, "login_server->client"),
                return_exceptions=True
            )
            
        except Exception as e:
            logger.error(f"Error in login protocol handling: {e}")
        finally:
            try:
                if 'server_writer' in locals():
                    server_writer.close()
                    await server_writer.wait_closed()
            except:
                pass
    
    async def _handle_game_protocol(self, client_reader, client_writer):
        """Handle game protocol by proxying to game server"""
        logger.info("Handling game protocol")
        
        try:
            # Connect to game server
            server_reader, server_writer = await asyncio.open_connection(
                self.game_host, self.game_port
            )
            
            # Start bidirectional proxy
            await asyncio.gather(
                self._proxy_data(client_reader, server_writer, "client->game_server"),
                self._proxy_data(server_reader, client_writer, "game_server->client"),
                return_exceptions=True
            )
            
        except Exception as e:
            logger.error(f"Error in game protocol handling: {e}")
        finally:
            try:
                if 'server_writer' in locals():
                    server_writer.close()
                    await server_writer.wait_closed()
            except:
                pass
    
    async def _proxy_data(self, reader, writer, direction: str):
        """Proxy data between reader and writer"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                
                writer.write(data)
                await writer.drain()
                
                # Optional: Log packet info (be careful with sensitive data)
                logger.debug(f"{direction}: {len(data)} bytes")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error proxying data ({direction}): {e}")
        finally:
            if not writer.is_closing():
                writer.close()
    
    async def stop(self):
        """Stop the proxy servers"""
        logger.info("Stopping Crystal Proxy...")
        
        # Close all active connections
        for writer in list(self.active_connections):
            if not writer.is_closing():
                writer.close()
        
        # Wait for connections to close
        if self.active_connections:
            await asyncio.gather(
                *[writer.wait_closed() for writer in self.active_connections 
                  if not writer.is_closing()],
                return_exceptions=True
            )
        
        # Stop TCP server
        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
        
        # Stop HTTP server
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("Crystal Proxy stopped")


class ImprovedCrystalProxy(CrystalProxy):
    """
    Improved version that runs HTTP and TCP on the same port
    by detecting the protocol from the first few bytes
    """
    
    def __init__(self, proxy_port: int = 7170, **kwargs):
        super().__init__(proxy_port, **kwargs)
        self.server = None
        
    async def start(self):
        """Start unified server on single port"""
        try:
            self.server = await asyncio.start_server(
                self.handle_connection,
                '0.0.0.0',
                self.proxy_port
            )
            
            logger.info(f"Crystal Proxy started on port {self.proxy_port}")
            logger.info("Listening for HTTP and TCP connections...")
            
        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            raise
    
    async def handle_connection(self, reader, writer):
        """Handle connection and detect if it's HTTP or TCP game protocol"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {client_addr}")
        
        self.active_connections.add(writer)
        
        try:
            # Read first bytes to detect protocol
            first_data = await reader.read(1024)
            if not first_data:
                return
            
            # Check if it's HTTP
            if self._is_http_request(first_data):
                await self._handle_http_connection(first_data, reader, writer)
            else:
                await self._handle_tcp_game_connection(first_data, reader, writer)
                
        except Exception as e:
            logger.error(f"Error handling connection from {client_addr}: {e}")
        finally:
            self.active_connections.discard(writer)
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
    
    def _is_http_request(self, data: bytes) -> bool:
        """Check if the data looks like an HTTP request"""
        try:
            # Check for HTTP methods
            http_methods = [b'GET ', b'POST ', b'PUT ', b'DELETE ', b'HEAD ', b'OPTIONS ']
            return any(data.startswith(method) for method in http_methods)
        except:
            return False
    
    async def _handle_http_connection(self, initial_data: bytes, reader, writer):
        """Handle HTTP connection"""
        try:
            # Parse HTTP request from initial_data + any remaining data
            request_data = initial_data
            
            # Read more data if needed (for complete HTTP request)
            while b'\r\n\r\n' not in request_data:
                more_data = await reader.read(1024)
                if not more_data:
                    break
                request_data += more_data
            
            # Parse HTTP request
            request_lines = request_data.decode('utf-8', errors='ignore').split('\r\n')
            if not request_lines:
                return
            
            method, path, version = request_lines[0].split(' ', 2)
            
            if method == 'POST' and path == '/login.php':
                await self._forward_http_login(request_data, writer)
            else:
                # Send 404 for other requests
                response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\n\r\nNot Found"
                writer.write(response)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Error handling HTTP connection: {e}")
    
    async def _forward_http_login(self, request_data: bytes, client_writer):
        """Forward HTTP login request to backend"""
        try:
            # Connect to HTTP backend
            backend_reader, backend_writer = await asyncio.open_connection(
                self.http_host, self.http_port
            )
            
            # Send request to backend
            backend_writer.write(request_data)
            await backend_writer.drain()
            
            # Read response from backend
            response_data = b""
            while True:
                data = await backend_reader.read(8192)
                if not data:
                    break
                response_data += data
                
                # Check if we have a complete HTTP response
                if b'\r\n\r\n' in response_data:
                    # Parse Content-Length if present
                    headers_end = response_data.find(b'\r\n\r\n')
                    headers = response_data[:headers_end].decode('utf-8', errors='ignore')
                    
                    content_length = None
                    for line in headers.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            content_length = int(line.split(':', 1)[1].strip())
                            break
                    
                    if content_length is not None:
                        total_expected = headers_end + 4 + content_length
                        if len(response_data) >= total_expected:
                            break
                    else:
                        # No content-length, assume response is complete
                        break
            
            # Send response to client
            client_writer.write(response_data)
            await client_writer.drain()
            
            # Close backend connection
            backend_writer.close()
            await backend_writer.wait_closed()
            
            logger.info("Forwarded HTTP login request successfully")
            
        except Exception as e:
            logger.error(f"Error forwarding HTTP login: {e}")
            # Send error response
            error_response = b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 21\r\n\r\nInternal Server Error"
            client_writer.write(error_response)
            await client_writer.drain()
    
    async def _handle_tcp_game_connection(self, initial_data: bytes, reader, writer):
        """Handle TCP game protocol connection"""
        try:
            # Detect if this is login or game protocol
            protocol_type = self._detect_game_protocol(initial_data)
            
            if protocol_type == "login":
                target_host, target_port = self.login_host, self.login_port
                logger.info("Proxying to login server")
            else:
                target_host, target_port = self.game_host, self.game_port
                logger.info("Proxying to game server")
            
            # Connect to target server
            server_reader, server_writer = await asyncio.open_connection(
                target_host, target_port
            )
            
            # Send initial data to server
            server_writer.write(initial_data)
            await server_writer.drain()
            
            # Start bidirectional proxy
            await asyncio.gather(
                self._proxy_data(reader, server_writer, "client->server"),
                self._proxy_data(server_reader, writer, "server->client"),
                return_exceptions=True
            )
            
        except Exception as e:
            logger.error(f"Error handling TCP game connection: {e}")
    
    def _detect_game_protocol(self, data: bytes) -> str:
        """Detect if this is login handshake or game session"""
        try:
            if len(data) < 3:
                return "game"  # Default to game
            
            # Check packet structure
            packet_length = struct.unpack('<H', data[:2])[0]
            
            # Simple heuristic: login packets are usually smaller
            if packet_length < 100:
                return "login"
            else:
                return "game"
                
        except:
            return "game"  # Default to game protocol
    
    async def stop(self):
        """Stop the proxy server"""
        logger.info("Stopping Crystal Proxy...")
        
        # Close all active connections
        for writer in list(self.active_connections):
            if not writer.is_closing():
                writer.close()
        
        # Wait for connections to close
        if self.active_connections:
            await asyncio.gather(
                *[writer.wait_closed() for writer in self.active_connections 
                  if not writer.is_closing()],
                return_exceptions=True
            )
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("Crystal Proxy stopped")


async def main():
    """Main function to run the proxy"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Crystal Server Proxy')
    parser.add_argument('--proxy-port', type=int, default=7170,
                       help='Port for the proxy to listen on (default: 7170)')
    parser.add_argument('--login-host', default='127.0.0.1',
                       help='Login server host (default: 127.0.0.1)')
    parser.add_argument('--login-port', type=int, default=7171,
                       help='Login server port (default: 7171)')
    parser.add_argument('--game-host', default='127.0.0.1',
                       help='Game server host (default: 127.0.0.1)')
    parser.add_argument('--game-port', type=int, default=7172,
                       help='Game server port (default: 7172)')
    parser.add_argument('--http-host', default='127.0.0.1',
                       help='HTTP login server host (default: 127.0.0.1)')
    parser.add_argument('--http-port', type=int, default=8090,
                       help='HTTP login server port (default: 8090)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create proxy instance
    proxy = ImprovedCrystalProxy(
        proxy_port=args.proxy_port,
        login_host=args.login_host,
        login_port=args.login_port,
        game_host=args.game_host,
        game_port=args.game_port,
        http_host=args.http_host,
        http_port=args.http_port
    )
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(proxy.stop())
    
    if sys.platform != 'win32':
        loop = asyncio.get_event_loop()
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, signal_handler)
    
    try:
        await proxy.start()
        
        # Keep running until stopped
        if proxy.server:
            async with proxy.server:
                await proxy.server.serve_forever()
                
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Proxy error: {e}")
    finally:
        await proxy.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProxy stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
