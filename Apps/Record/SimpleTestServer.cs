using System;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;

namespace Record
{
    public class SimpleTestServer
    {
        private TcpListener _tcpListener;
        private bool _isRunning;
        private readonly int _port;

        public SimpleTestServer(int port = 7172)
        {
            _port = port;
        }

        public async Task Start()
        {
            _tcpListener = new TcpListener(IPAddress.Any, _port);
            _tcpListener.Start();
            _isRunning = true;

            Console.WriteLine($"Test server started on port {_port}");
            Console.WriteLine("Waiting for connections...");

            while (_isRunning)
            {
                try
                {
                    var tcpClient = await _tcpListener.AcceptTcpClientAsync();
                    Console.WriteLine($"Client connected from {tcpClient.Client.RemoteEndPoint}");
                    
                    // Handle client in background
                    _ = Task.Run(() => HandleClient(tcpClient));
                }
                catch (Exception ex) when (_isRunning)
                {
                    Console.WriteLine($"Error accepting client: {ex.Message}");
                }
            }
        }

        private async Task HandleClient(TcpClient client)
        {
            try
            {
                var buffer = new byte[2048];
                var stream = client.GetStream();

                Console.WriteLine("=== New Client Connection ===");

                while (client.Connected && _isRunning)
                {
                    var bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length);
                    if (bytesRead == 0)
                    {
                        Console.WriteLine("Client disconnected normally");
                        break;
                    }

                    Console.WriteLine($"Received {bytesRead} bytes from client:");
                    Console.WriteLine($"  Hex: {BitConverter.ToString(buffer, 0, bytesRead)}");
                    
                    // Parse Tibia packet structure
                    if (bytesRead >= 2)
                    {
                        var packetLength = BitConverter.ToUInt16(buffer, 0);
                        Console.WriteLine($"  Packet length: {packetLength}");
                        Console.WriteLine($"  Total expected size: {packetLength + 2} bytes (including length header)");
                        
                        if (bytesRead >= 6)
                        {
                            // Skip length (2 bytes) and get packet type
                            Console.WriteLine($"  Packet type: 0x{buffer[2]:X2}");
                            Console.WriteLine($"  Full packet: {BitConverter.ToString(buffer, 0, Math.Min(bytesRead, (int)packetLength + 2))}");
                        }

                        // Simulate the same issue - send a response claiming to be longer than it is
                        // This will help test if the proxy can handle malformed packets
                        var malformedResponse = new byte[] { 
                            0x8D, 0x03, // Claims to be 909 bytes
                            0x0A,       // Packet type
                            0x01, 0x1F, 0x36, 0x79, 0xD1, 0x68, 0x8B, 0x71, 0x00, 0x00, 0x00, 0x00 
                        }; // But only 15 bytes total
                        
                        await stream.WriteAsync(malformedResponse, 0, malformedResponse.Length);
                        Console.WriteLine($"Sent malformed response (claims 909 bytes, actually {malformedResponse.Length}): {BitConverter.ToString(malformedResponse)}");
                        
                        // Close connection after sending malformed packet to simulate server behavior
                        Console.WriteLine("Closing connection to simulate server behavior");
                        break;
                    }
                    else
                    {
                        // For packets smaller than 2 bytes, send a proper response
                        var response = new byte[] { 0x04, 0x00, 0x0A, 0x01 }; // Simple 4-byte packet
                        await stream.WriteAsync(response, 0, response.Length);
                        Console.WriteLine($"Sent simple response: {BitConverter.ToString(response)}");
                    }
                }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error handling client: {ex.Message}");
            }
            finally
            {
                client?.Close();
                Console.WriteLine("Client connection closed");
            }
        }

        public void Stop()
        {
            _isRunning = false;
            _tcpListener?.Stop();
            Console.WriteLine("Test server stopped");
        }
    }
}
