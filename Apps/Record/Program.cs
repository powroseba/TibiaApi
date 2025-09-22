using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

using OXGaming.TibiaAPI;
using OXGaming.TibiaAPI.Constants;
using OXGaming.TibiaAPI.Utilities;

namespace Record
{
    class Message
    {
        public byte[] Data { get; set; }

        public long Timestamp { get; set; }

        public PacketType Type { get; set; }
    }

    class Program
    {
        static readonly ConcurrentQueue<Message> _fileWriteQueue = new ConcurrentQueue<Message>();

        static readonly Stopwatch _stopWatch = new Stopwatch();

        static BinaryWriter _binaryWriter;

        static Client _client;

        static FileStream _fileStream;

        static Thread _fileWriteThread;

        private static Logger.LogLevel _logLevel = Logger.LogLevel.Debug;

        private static Logger.LogOutput _logOutput = Logger.LogOutput.Console;

        static string _loginWebService = string.Empty;
        static string _tibiaDirectory = string.Empty;
        static string _gameServerHost = "127.0.0.1";
        static int _gameServerPort = 7172;
        static bool _enableRecording = false;
        static bool _useLocalServer = false;
        static bool _startTestServer = false;
        static SimpleTestServer _testServer;

        static int _httpPort = 7171;

        static bool _isWritingToFile = false;

        static void ParseArgs(string[] args)
        {
            foreach (var arg in args)
            {
                if (!arg.Contains('=', StringComparison.CurrentCultureIgnoreCase))
                {
                    continue;
                }

                var splitArg = arg.Split('=');
                if (splitArg.Length != 2)
                {
                    continue;
                }

                switch (splitArg[0])
                {
                    case "-t":
                    case "--tibiadirectory":
                        {
                            _tibiaDirectory = splitArg[1].Replace("\"", "");
                        }
                        break;
                    case "-p":
                    case "--port":
                        {
                            if (int.TryParse(splitArg[1], out var port))
                            {
                                _httpPort = port;
                            }
                        }
                        break;
                    case "-l":
                    case "--login":
                        {
                            _loginWebService = splitArg[1];
                        }
                        break;
                    case "-s":
                    case "--server":
                        {
                            _gameServerHost = splitArg[1];
                        }
                        break;
                    case "-sp":
                    case "--serverport":
                        {
                            if (int.TryParse(splitArg[1], out var serverPort))
                            {
                                _gameServerPort = serverPort;
                            }
                        }
                        break;
                    case "-r":
                    case "--record":
                        {
                            if (bool.TryParse(splitArg[1], out var record))
                            {
                                _enableRecording = record;
                            }
                        }
                        break;
                    case "--local":
                        {
                            if (bool.TryParse(splitArg[1], out var useLocal))
                            {
                                _useLocalServer = useLocal;
                            }
                        }
                        break;
                    case "--testserver":
                        {
                            if (bool.TryParse(splitArg[1], out var startTest))
                            {
                                _startTestServer = startTest;
                            }
                        }
                        break;
                    case "--loglevel":
                        {
                            _logLevel = Logger.ConvertToLogLevel(splitArg[1]);
                        }
                        break;
                    case "--logoutput":
                        {
                            _logOutput = Logger.ConvertToLogOutput(splitArg[1]);
                        }
                        break;
                    default:
                        break;
                }
            }
        }

        static async Task Main(string[] args)
        {
            try
            {
                ParseArgs(args);

                // Print out the raw args
                Console.WriteLine("Arguments:");
                foreach (var arg in args)
                {
                    Console.WriteLine("  " + arg);
                }

                // Print out the parsed Tibia directory specifically
                Console.WriteLine($"Parsed tibiaDirectory = '{_tibiaDirectory}'");
                Console.WriteLine($"Parsed loginWebService = '{_loginWebService}'");
                Console.WriteLine($"Parsed httpPort = {_httpPort}");
                Console.WriteLine($"Parsed gameServerHost = '{_gameServerHost}'");
                Console.WriteLine($"Parsed gameServerPort = {_gameServerPort}");
                Console.WriteLine($"Parsed enableRecording = {_enableRecording}");
                Console.WriteLine($"Parsed useLocalServer = {_useLocalServer}");
                Console.WriteLine($"Parsed startTestServer = {_startTestServer}");

                if (!string.IsNullOrEmpty(_loginWebService))
                {
                    Console.WriteLine($"Using custom login service: {_loginWebService}");
                    Console.WriteLine("This will override the default Tibia login service.");
                }
                else 
                {
                    Console.WriteLine("Using default Tibia login service (https://www.tibia.com/clientservices/loginservice.php)");
                }

                // Start test server if requested
                if (_startTestServer)
                {
                    _testServer = new SimpleTestServer(_gameServerPort);
                    Console.WriteLine($"Starting test server on port {_gameServerPort}...");
                    _ = Task.Run(async () => await _testServer.Start());
                    await Task.Delay(1000); // Give server time to start
                }

                if (_useLocalServer)
                {
                    Console.WriteLine("WARNING: Local server mode enabled!");
                    Console.WriteLine($"Make sure your server is running on {_gameServerHost}:{_gameServerPort}");
                    Console.WriteLine("The proxy will attempt to redirect connections to your local server.");
                }

                using (_client = new Client(_tibiaDirectory))
                {
                    Console.CancelKeyPress += Console_CancelKeyPress;

                    // Only setup recording if enabled
                    if (_enableRecording)
                    {
                        var utcNow = DateTime.UtcNow;
                        var filename = $"{utcNow.Day}_{utcNow.Month}_{utcNow.Year}__{utcNow.Hour}_{utcNow.Minute}_{utcNow.Second}.oxr";
                        var recordingDirectory = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Recordings");
                        if (!Directory.Exists(recordingDirectory))
                        {
                            Directory.CreateDirectory(recordingDirectory);
                        }

                        _fileStream = new FileStream(Path.Combine(recordingDirectory, filename), FileMode.Append);
                        _binaryWriter = new BinaryWriter(_fileStream);
                        _binaryWriter.Write(_client.Version);
                        
                        Console.WriteLine($"Recording enabled. Saving to: {filename}");
                    }
                    else
                    {
                        Console.WriteLine("Recording disabled. Acting as proxy only.");
                    }

                    _client.Logger.Level = _logLevel;
                    _client.Logger.Output = _logOutput;

                    // Configure local server override if enabled
                    if (_useLocalServer)
                    {
                        _client.Connection.UseLocalServer = true;
                        _client.Connection.LocalServerHost = _gameServerHost;
                        _client.Connection.LocalServerPort = _gameServerPort;
                        Console.WriteLine($"Local server override enabled: {_gameServerHost}:{_gameServerPort}");
                    }

                    _client.Connection.OnReceivedClientMessage += Proxy_OnReceivedClientMessage;
                    _client.Connection.OnReceivedServerMessage += Proxy_OnReceivedServerMessage;

                    // Enable packet parsing for proxy functionality
                    _client.Connection.IsClientPacketParsingEnabled = true;
                    _client.Connection.IsServerPacketParsingEnabled = true;
                    _client.StartConnection(httpPort: _httpPort, loginWebService: _loginWebService);

                    while (Console.ReadLine() != "quit") { }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex);
            }
            finally
            {
                Shutdown();
            }
        }

        private static void Console_CancelKeyPress(object sender, ConsoleCancelEventArgs e)
        {
            Shutdown();
        }

        private static void Shutdown()
        {
            if (_testServer != null)
            {
                _testServer.Stop();
                Console.WriteLine("Test server stopped.");
            }

            if (_client != null)
            {
                _client.StopConnection();

                _client.Connection.OnReceivedClientMessage -= Proxy_OnReceivedClientMessage;
                _client.Connection.OnReceivedServerMessage -= Proxy_OnReceivedServerMessage;
            }

            if (_enableRecording && _fileWriteThread != null)
            {
                // Block the application from shutting down until the file-write thread
                // finishes writing all incoming packets to disk. This is safe to do as
                // the proxy connection will have been stopped, no matter what, by now.
                _fileWriteThread.Join();
            }

            if (_binaryWriter != null)
            {
                _binaryWriter.Close();
            }

            if (_fileStream != null)
            {
                _fileStream.Close();
            }

            if (_stopWatch.IsRunning)
            {
                _stopWatch.Stop();
            }
        }

        private static void Proxy_OnReceivedClientMessage(byte[] data)
        {
            if (_enableRecording)
            {
                QueueMessage(PacketType.Client, data);
            }
        }

        private static void Proxy_OnReceivedServerMessage(byte[] data)
        {
            if (_enableRecording)
            {
                QueueMessage(PacketType.Server, data);
            }
        }

        private static void QueueMessage(PacketType packetType, byte[] data)
        {
            if (!_stopWatch.IsRunning)
            {
                _stopWatch.Start();
            }

            var packetData = new Message
            {
                Data = data,
                Timestamp = _stopWatch.ElapsedMilliseconds,
                Type = packetType
            };

            _fileWriteQueue.Enqueue(packetData);

            if (!_isWritingToFile)
            {
                try
                {
                    _isWritingToFile = true;
                    _fileWriteThread = new Thread(new ThreadStart(WriteData));
                    _fileWriteThread.Start();
                }
                catch (Exception ex)
                {
                    Console.WriteLine(ex);
                }
            }
        }

        private static void WriteData()
        {
            try
            {
                while (_fileWriteQueue.TryDequeue(out var packet))
                {
                    _binaryWriter.Write((byte)packet.Type);
                    _binaryWriter.Write(packet.Timestamp);
                    _binaryWriter.Write(packet.Data.Length);
                    _binaryWriter.Write(packet.Data);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex);
            }
            finally
            {
                _isWritingToFile = false;
            }
        }
    }
}
