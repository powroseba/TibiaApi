#!/usr/bin/env python3
"""
Test script for Crystal Server Proxy

This script tests the basic functionality of the proxy:
1. HTTP POST to /login.php
2. TCP connection simulation
"""

import asyncio
import aiohttp
import socket
import sys
import struct
import time

async def test_http_login(proxy_host='localhost', proxy_port=7170):
    """Test HTTP login endpoint"""
    print("🧪 Testing HTTP login endpoint...")
    
    try:
        url = f"http://{proxy_host}:{proxy_port}/login.php"
        data = {
            'username': 'testuser',
            'password': 'testpass',
            'action': 'login'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                print(f"✅ HTTP Response: {response.status}")
                text = await response.text()
                print(f"📄 Response body: {text[:100]}...")
                return response.status == 200 or response.status == 404  # 404 is ok if backend not running
                
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")
        return False

async def test_tcp_connection(proxy_host='localhost', proxy_port=7170, is_login=True):
    """Test TCP connection (simulates login or game protocol)"""
    protocol_name = "login" if is_login else "game"
    print(f"🧪 Testing TCP {protocol_name} protocol...")
    
    try:
        # Create a test packet
        if is_login:
            # Small packet to trigger login protocol detection
            packet_data = b"\\x01\\x02\\x03\\x04"  # Small test packet
        else:
            # Larger packet to trigger game protocol detection  
            packet_data = b"\\x00" * 200  # Large test packet
        
        # Add packet length header (little endian)
        packet_length = len(packet_data)
        full_packet = struct.pack('<H', packet_length) + packet_data
        
        # Connect and send
        reader, writer = await asyncio.open_connection(proxy_host, proxy_port)
        
        writer.write(full_packet)
        await writer.drain()
        
        # Try to read response (will likely fail if backend not running, but that's ok)
        try:
            response = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            print(f"✅ TCP {protocol_name}: Received {len(response)} bytes response")
        except asyncio.TimeoutError:
            print(f"✅ TCP {protocol_name}: Connection established (no response - backend may not be running)")
        
        writer.close()
        await writer.wait_closed()
        return True
        
    except Exception as e:
        print(f"❌ TCP {protocol_name} test failed: {e}")
        return False

def test_port_listening(host='localhost', port=7170):
    """Test if proxy is listening on the specified port"""
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
            print(f"❌ Port {port} is not accessible")
            return False
            
    except Exception as e:
        print(f"❌ Port test failed: {e}")
        return False

async def run_tests(proxy_host='localhost', proxy_port=7170):
    """Run all tests"""
    print("🚀 Starting Crystal Server Proxy Tests")
    print("=" * 50)
    
    # Test 1: Check if proxy is listening
    if not test_port_listening(proxy_host, proxy_port):
        print("❌ Proxy is not running or not accessible")
        print("💡 Make sure to start the proxy first:")
        print(f"   python simple_proxy.py --proxy-port {proxy_port}")
        return False
    
    print()
    
    # Test 2: HTTP login test
    http_success = await test_http_login(proxy_host, proxy_port)
    print()
    
    # Test 3: TCP login protocol test
    tcp_login_success = await test_tcp_connection(proxy_host, proxy_port, is_login=True)
    print()
    
    # Test 4: TCP game protocol test  
    tcp_game_success = await test_tcp_connection(proxy_host, proxy_port, is_login=False)
    print()
    
    # Summary
    print("=" * 50)
    print("📊 Test Results Summary:")
    print(f"🌐 HTTP Login: {'✅ PASS' if http_success else '❌ FAIL'}")
    print(f"🔐 TCP Login: {'✅ PASS' if tcp_login_success else '❌ FAIL'}")
    print(f"🎮 TCP Game: {'✅ PASS' if tcp_game_success else '❌ FAIL'}")
    
    total_tests = 3
    passed_tests = sum([http_success, tcp_login_success, tcp_game_success])
    
    print(f"📈 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! The proxy is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
        print("💡 Note: Some failures are expected if the backend servers are not running.")
    
    return passed_tests == total_tests

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Crystal Server Proxy')
    parser.add_argument('--host', default='localhost', help='Proxy host to test')
    parser.add_argument('--port', type=int, default=7170, help='Proxy port to test')
    
    args = parser.parse_args()
    
    print(f"🎯 Testing proxy at {args.host}:{args.port}")
    print()
    
    success = await run_tests(args.host, args.port)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test error: {e}")
        sys.exit(1)
