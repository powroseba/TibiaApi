using OXGaming.TibiaAPI.Constants;

namespace OXGaming.TibiaAPI.Network.ClientPackets
{
    public class BossSlots : ClientPacket
    {

        public BossSlots(Client client)
        {
            Client = client;
            PacketType = ClientPacketType.BossSlots;
        }

        public override void ParseFromNetworkMessage(NetworkMessage message)
        {
        }

        public override void AppendToNetworkMessage(NetworkMessage message)
        {
            message.Write((byte)ClientPacketType.BossSlots);
        }
    }
}
