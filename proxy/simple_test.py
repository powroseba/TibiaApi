#!/usr/bin/env python3
"""
Simple test for Crystal Server Proxy (no external dependencies)
"""

import asyncio
import socket
import struct
import sys
import time

def test_port_open(host='localhost', port=7170):
    """Test if the proxy port is open"""
    print(f"🧪 Testing if proxy is listening on {host}:{port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is open and accepting connections")
            return True
        else:
            print(f"❌ Port {port} is not accessible (Error code: {result})")
            return False
            
    except Exception as e:
        print(f"❌ Port test failed: {e}")
        return False

async def test_tcp_connection(host='localhost', port=7170):
    """Test basic TCP connection to proxy"""
    print(f"🧪 Testing TCP connection to {host}:{port}...")
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), 
            timeout=5.0
        )
        
        print("✅ TCP connection established")
        
        # Send a test HTTP request
        http_request = (
            b"POST /login.php HTTP/1.1\\r\\n"
            b"Host: localhost\\r\\n"
            b"Content-Type: application/x-www-form-urlencoded\\r\\n"
            b"Content-Length: 23\\r\\n"
            b"\\r\\n"
            b"username=test&password=test"
        )
        
        writer.write(http_request)
        await writer.drain()
        print("📤 Sent HTTP login request")
        
        # Try to read response
        try:
            response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
            if response:
                print(f"📨 Received response: {len(response)} bytes")
                # Check if it looks like HTTP response
                if response.startswith(b"HTTP/"):
                    status_line = response.split(b"\\r\\n")[0].decode()
                    print(f"📄 HTTP Status: {status_line}")
                else:
                    print(f"📄 Response preview: {response[:50]}...")
            else:
                print("📭 No response received")
        except asyncio.TimeoutError:
            print("⏰ No response within timeout (backend may not be running)")
        
        writer.close()
        await writer.wait_closed()
        print("🔌 Connection closed")
        return True
        
    except asyncio.TimeoutError:
        print("⏰ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ TCP connection test failed: {e}")
        return False

async def test_tcp_game_protocol(host='localhost', port=7170):
    """Test TCP connection with game-like data"""
    print(f"🧪 Testing TCP game protocol simulation...")
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), 
            timeout=5.0
        )
        
        # Create a larger packet that should be detected as game protocol
        game_data = b"\\x00" * 200  # Large packet
        packet_length = len(game_data)
        full_packet = struct.pack('<H', packet_length) + game_data
        
        writer.write(full_packet)
        await writer.drain()
        print("📤 Sent game protocol packet")
        
        # Try to read response
        try:
            response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
            print(f"📨 Game protocol response: {len(response)} bytes")
        except asyncio.TimeoutError:
            print("⏰ No game response (backend may not be running)")
        
        writer.close()
        await writer.wait_closed()
        return True
        
    except Exception as e:
        print(f"❌ Game protocol test failed: {e}")
        return False

def print_instructions():
    """Print usage instructions"""
    print("📋 Crystal Server Proxy Test")
    print("=" * 40)
    print("This script tests the basic functionality of the proxy.")
    print()
    print("🚀 To run the proxy first:")
    print("   python simple_proxy.py --proxy-port 7170")
    print()
    print("🧪 Then run this test:")
    print("   python simple_test.py")
    print()

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Crystal Server Proxy Test')
    parser.add_argument('--host', default='localhost', help='Proxy host')
    parser.add_argument('--port', type=int, default=7170, help='Proxy port')
    
    args = parser.parse_args()
    
    print_instructions()
    
    print(f"🎯 Testing proxy at {args.host}:{args.port}")
    print()
    
    # Test 1: Port open
    port_open = test_port_open(args.host, args.port)
    print()
    
    if not port_open:
        print("❌ Proxy is not running. Please start it first:")
        print(f"   python simple_proxy.py --proxy-port {args.port}")
        return False
    
    # Test 2: HTTP-like connection
    http_test = await test_tcp_connection(args.host, args.port)
    print()
    
    # Test 3: Game protocol simulation
    game_test = await test_tcp_game_protocol(args.host, args.port)
    print()
    
    # Summary
    print("=" * 40)
    print("📊 Test Results:")
    print(f"🔌 Port Open: {'✅ PASS' if port_open else '❌ FAIL'}")
    print(f"🌐 HTTP Test: {'✅ PASS' if http_test else '❌ FAIL'}")
    print(f"🎮 Game Test: {'✅ PASS' if game_test else '❌ FAIL'}")
    
    passed = sum([port_open, http_test, game_test])
    total = 3
    
    print(f"📈 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Proxy is working.")
    else:
        print("⚠️  Some tests failed. This may be normal if backend servers aren't running.")
    
    return passed >= 2  # Consider success if at least port and one protocol work

if __name__ == '__main__':
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\\n🛑 Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test error: {e}")
        sys.exit(1)
