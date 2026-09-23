package agrilorasec;

import inet.applications.contract.IApp;

// Remplace flora.PacketForwarder : meme comportement + journalisation RSSI/SNIR/seq
simple LoggingPacketForwarder like IApp
{
    parameters:
        @class(agrilorasec::LoggingPacketForwarder);
        @signal[LoRa_GWPacketReceived](type=long);
        @statistic[LoRa_GWPacketReceived](source=LoRa_GWPacketReceived; record=count);
        int localPort = default(-1);
        string destAddresses = default("");
        string localAddress = default("");
        int destPort;
        int indexNumber = default(0);

        // Filtre anti-replay / anti-doublon wormhole (MAC + sequenceNumber).
        // Desactive par defaut : campagnes V2/V3 inchangees.
        bool enableDuplicateFilter = default(false);
        string securityLogFile = default("results/security_events.csv");

    gates:
        output socketOut @labels(UdpControlInfo/up);
        input socketIn @labels(UdpControlInfo/down);
        input lowerLayerIn @labels(PacketForwarder/up);
        output lowerLayerOut @labels(PacketForwarder/down);
}
