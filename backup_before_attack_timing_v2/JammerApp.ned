package agrilorasec;

import inet.applications.contract.IApp;

// Application d'attaque : jamming LoRa
// Envoie tres frequemment pour perturber le canal
simple JammerApp like IApp
{
    parameters:
        @class(agrilorasec::JammerApp);
        @display("i=block/erouter");
        @signal[jammingPacketSent](type=long);
        @statistic[jammingPacketSent](source=jammingPacketSent; record=count);

        int numberOfPacketsToSend = default(0); // 0 = infini
        volatile double timeToFirstPacket @unit(s) = default(1s);
        volatile double timeToNextPacket @unit(s) = default(0.05s);

        double initialLoRaTP @unit(dBm) = default(14dBm);
        double initialLoRaCF @unit(Hz) = default(868MHz);
        int initialLoRaSF = default(12);
        double initialLoRaBW @unit(Hz) = default(125kHz);
        int initialLoRaCR = default(4);
        bool initialUseHeader = default(true);
        int dataSize @unit(B) = default(20B);

    gates:
        input socketIn @labels(LoRaAppPacket/up);
        output socketOut @labels(LoRaAppPacket/down);
}
