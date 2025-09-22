using System;
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
                var buffer = new byte[1024];
                var stream = client.GetStream();

                while (client.Connected && _isRunning)
                {
                    var bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length);
                    if (bytesRead == 0)
                    {
                        Console.WriteLine("Client disconnected");
                        break;
                    }

                    Console.WriteLine($"Received {bytesRead} bytes from client:");
                    Console.WriteLine($"  Hex: {BitConverter.ToString(buffer, 0, bytesRead)}");
                    
                    // Try to interpret as string if printable
                    var text = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    if (!string.IsNullOrWhiteSpace(text))
                    {
                        Console.WriteLine($"  Text: {text.Replace("\n", "\\n").Replace("\r", "\\r")}");
                    }

                    // Echo back the data for now
                    await stream.WriteAsync(buffer, 0, bytesRead);
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
