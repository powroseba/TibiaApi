#!/usr/bin/env python3
"""
Simple Crystal Server Proxy

A lightweight proxy for CrystalServer that handles:
1. HTTP POST /login.php -> forwards to backend HTTP server
2. TCP connections for login handshake (port 7171) 
3. TCP connections for game sessions (port 7172)

Usage:
    python simple_proxy.py --proxy-port 7170

Client connects to: localhost:7170
"""

import asyncio
import logging
import struct
import sys
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleGameProxy:
    def __init__(self, 
                 proxy_port: int = 7170,
                 backend_login_host: str = "127.0.0.1",
                 backend_login_port: int = 7171,
                 backend_game_host: str = "127.0.0.1", 
                 backend_game_port: int = 7172,
                 backend_http_host: str = "127.0.0.1",
                 backend_http_port: int = 8090):
        
        self.proxy_port = proxy_port
        self.backend_login_host = backend_login_host
        self.backend_login_port = backend_login_port
        self.backend_game_host = backend_game_host
        self.backend_game_port = backend_game_port
        self.backend_http_host = backend_http_host
        self.backend_http_port = backend_http_port
        
        self.server = None
        self.active_connections = set()
        
    async def start(self):
        """Start the proxy server"""
        try:
            self.server = await asyncio.start_server(
                self.handle_connection,
                '0.0.0.0',
                self.proxy_port
            )
            
            logger.info(f"🎮 Crystal Server Proxy started on port {self.proxy_port}")
            logger.info(f"📡 Backend Login: {self.backend_login_host}:{self.backend_login_port}")
            logger.info(f"🎯 Backend Game: {self.backend_game_host}:{self.backend_game_port}")
            logger.info(f"🌐 Backend HTTP: {self.backend_http_host}:{self.backend_http_port}")
            logger.info("✅ Ready to accept connections...")
            
            async with self.server:
                await self.server.serve_forever()
                
        except Exception as e:
            logger.error(f"❌ Failed to start proxy: {e}")
            raise
    
    async def handle_connection(self, reader, writer):
        """Handle incoming connection and route appropriately"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"🔗 New connection from {client_addr}")
        
        self.active_connections.add(writer)
        
        try:
            # Read initial data to determine protocol type
            initial_data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            
            if not initial_data:
                logger.warning(f"❌ No data received from {client_addr}")
                return
            
            # Detect protocol type
            if self._is_http_request(initial_data):
                await self._handle_http(initial_data, reader, writer, client_addr)
            else:
                await self._handle_tcp_game(initial_data, reader, writer, client_addr)
                
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Connection timeout from {client_addr}")
        except Exception as e:
            logger.error(f"❌ Error handling connection from {client_addr}: {e}")
        finally:
            self.active_connections.discard(writer)
            if not writer.is_closing():
                writer.close()
                try:
                    await writer.wait_closed()
                except:
                    pass
    
    def _is_http_request(self, data: bytes) -> bool:
        """Check if data looks like HTTP request"""
        try:
            # Check for HTTP methods at start of data
            http_methods = [b'GET ', b'POST ', b'PUT ', b'DELETE ', b'HEAD ', b'OPTIONS ']
            return any(data.startswith(method) for method in http_methods)
        except:
            return False
    
    async def _handle_http(self, initial_data: bytes, reader, writer, client_addr):
        """Handle HTTP requests (login.php)"""
        try:
            logger.info(f"🌐 HTTP request from {client_addr}")
            
            # Read complete HTTP request
            request_data = initial_data
            
            # Continue reading until we have complete request
            while b'\\r\\n\\r\\n' not in request_data:
                more_data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
                if not more_data:
                    break
                request_data += more_data
            
            # Parse request line
            request_lines = request_data.decode('utf-8', errors='ignore').split('\\r\\n')
            if not request_lines:
                return
            
            method, path, version = request_lines[0].split(' ', 2)
            logger.info(f"📨 {method} {path}")
            
            if method == 'POST' and path == '/login.php':
                await self._forward_http_login(request_data, writer)
            else:
                # Send 404 for other requests
                response = (
                    b"HTTP/1.1 404 Not Found\\r\\n"
                    b"Content-Type: text/plain\\r\\n"
                    b"Content-Length: 9\\r\\n"
                    b"\\r\\n"
                    b"Not Found"
                )
                writer.write(response)
                await writer.drain()
                logger.info(f"📤 Sent 404 for {path}")
                
        except Exception as e:
            logger.error(f"❌ HTTP error: {e}")
            # Send 500 error
            try:
                error_response = (
                    b"HTTP/1.1 500 Internal Server Error\\r\\n"
                    b"Content-Length: 21\\r\\n"
                    b"\\r\\n"
                    b"Internal Server Error"
                )
                writer.write(error_response)
                await writer.drain()
            except:
                pass
    
    async def _forward_http_login(self, request_data: bytes, client_writer):
        """Forward login.php request to backend HTTP server"""
        try:
            logger.info("🔄 Forwarding login request to backend...")
            
            # Connect to backend HTTP server
            backend_reader, backend_writer = await asyncio.open_connection(
                self.backend_http_host, self.backend_http_port
            )
            
            # Send request to backend
            backend_writer.write(request_data)
            await backend_writer.drain()
            
            # Read response from backend
            response_data = await self._read_http_response(backend_reader)
            
            # Send response to client
            client_writer.write(response_data)
            await client_writer.drain()
            
            # Close backend connection
            backend_writer.close()
            await backend_writer.wait_closed()
            
            logger.info("✅ Login request forwarded successfully")
            
        except Exception as e:
            logger.error(f"❌ Error forwarding login: {e}")
            raise
    
    async def _read_http_response(self, reader) -> bytes:
        """Read complete HTTP response"""
        response_data = b""
        headers_complete = False
        content_length = None
        
        while True:
            data = await reader.read(8192)
            if not data:
                break
                
            response_data += data
            
            if not headers_complete and b'\\r\\n\\r\\n' in response_data:
                headers_complete = True
                headers_end = response_data.find(b'\\r\\n\\r\\n')
                headers = response_data[:headers_end].decode('utf-8', errors='ignore')
                
                # Parse Content-Length
                for line in headers.split('\\r\\n'):
                    if line.lower().startswith('content-length:'):
                        content_length = int(line.split(':', 1)[1].strip())
                        break
            
            if headers_complete and content_length is not None:
                headers_end = response_data.find(b'\\r\\n\\r\\n')
                body_length = len(response_data) - (headers_end + 4)
                if body_length >= content_length:
                    break
            elif headers_complete and content_length is None:
                # No content-length, read a bit more and assume complete
                await asyncio.sleep(0.1)
                break
        
        return response_data
    
    async def _handle_tcp_game(self, initial_data: bytes, reader, writer, client_addr):
        """Handle TCP game protocol connections"""
        try:
            # Determine if this is login handshake or game session
            protocol_type = self._detect_protocol_type(initial_data)
            
            if protocol_type == "login":
                target_host = self.backend_login_host
                target_port = self.backend_login_port
                logger.info(f"🔐 Login handshake from {client_addr}")
            else:
                target_host = self.backend_game_host  
                target_port = self.backend_game_port
                logger.info(f"🎮 Game session from {client_addr}")
            
            # Connect to appropriate backend server
            backend_reader, backend_writer = await asyncio.open_connection(
                target_host, target_port
            )
            
            logger.info(f"🔗 Connected to {target_host}:{target_port}")
            
            # Send initial data to backend
            backend_writer.write(initial_data)
            await backend_writer.drain()
            
            # Start bidirectional data forwarding
            await asyncio.gather(
                self._forward_data(reader, backend_writer, f"{client_addr}->backend"),
                self._forward_data(backend_reader, writer, f"backend->{client_addr}"),
                return_exceptions=True
            )
            
        except Exception as e:
            logger.error(f"❌ TCP protocol error: {e}")
        finally:
            # Clean up backend connection
            try:
                if 'backend_writer' in locals() and not backend_writer.is_closing():
                    backend_writer.close()
                    await backend_writer.wait_closed()
            except:
                pass
    
    def _detect_protocol_type(self, data: bytes) -> str:
        """
        Detect if this is login handshake or game session.
        
        Based on Crystal Server protocol patterns:
        - Login packets are typically smaller (< 200 bytes)
        - Game packets can be larger
        - Can also check specific opcodes if known
        """
        try:
            if len(data) < 3:
                return "game"  # Default assumption
            
            # Read packet length (first 2 bytes, little endian)
            packet_length = struct.unpack('<H', data[:2])[0]
            
            # Heuristic: login handshakes are usually smaller packets
            if packet_length < 150:
                logger.debug(f"🔍 Small packet ({packet_length} bytes) -> login protocol")
                return "login"
            else:
                logger.debug(f"🔍 Large packet ({packet_length} bytes) -> game protocol")
                return "game"
                
        except Exception as e:
            logger.debug(f"🔍 Protocol detection error: {e}, defaulting to game")
            return "game"
    
    async def _forward_data(self, source_reader, dest_writer, direction: str):
        """Forward data from source to destination"""
        try:
            bytes_transferred = 0
            while True:
                data = await source_reader.read(8192)
                if not data:
                    logger.debug(f"📡 {direction}: Connection closed ({bytes_transferred} bytes)")
                    break
                
                dest_writer.write(data)
                await dest_writer.drain()
                bytes_transferred += len(data)
                
                # Log data transfer (optional, can be verbose)
                if len(data) > 0:
                    logger.debug(f"📡 {direction}: {len(data)} bytes")
                
        except asyncio.CancelledError:
            logger.debug(f"📡 {direction}: Transfer cancelled")
        except Exception as e:
            logger.debug(f"📡 {direction}: Transfer error: {e}")
        finally:
            if not dest_writer.is_closing():
                dest_writer.close()
    
    async def stop(self):
        """Stop the proxy server"""
        logger.info("🛑 Stopping proxy...")
        
        # Close active connections
        for writer in list(self.active_connections):
            if not writer.is_closing():
                writer.close()
        
        # Wait for connections to close
        if self.active_connections:
            await asyncio.gather(
                *[writer.wait_closed() for writer in self.active_connections],
                return_exceptions=True
            )
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("✅ Proxy stopped")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Simple Crystal Server Proxy',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--proxy-port', type=int, default=7170,
                       help='Port for proxy to listen on')
    parser.add_argument('--login-host', default='127.0.0.1',
                       help='Backend login server host')
    parser.add_argument('--login-port', type=int, default=7171,
                       help='Backend login server port')
    parser.add_argument('--game-host', default='127.0.0.1',
                       help='Backend game server host')
    parser.add_argument('--game-port', type=int, default=7172,
                       help='Backend game server port')
    parser.add_argument('--http-host', default='127.0.0.1',
                       help='Backend HTTP server host')
    parser.add_argument('--http-port', type=int, default=8090,
                       help='Backend HTTP server port')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    proxy = SimpleGameProxy(
        proxy_port=args.proxy_port,
        backend_login_host=args.login_host,
        backend_login_port=args.login_port,
        backend_game_host=args.game_host,
        backend_game_port=args.game_port,
        backend_http_host=args.http_host,
        backend_http_port=args.http_port
    )
    
    try:
        await proxy.start()
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal")
    finally:
        await proxy.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n🛑 Proxy stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
