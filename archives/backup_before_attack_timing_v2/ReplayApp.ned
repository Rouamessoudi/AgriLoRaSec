package agrilorasec;

import inet.applications.contract.IApp;

// Application d'attaque : replay LoRa
// Simule la capture puis le renvoi d'un paquet legitime
simple ReplayApp like IApp
{
    parameters:
        @class(agrilorasec::ReplayApp);
        @display("i=block/erouter");
        @signal[replayPacketSent](type=long);
        @statistic[replayPacketSent](source=replayPacketSent; record=count);

        volatile double timeToCapture @unit(s) = default(5s);
        volatile double timeToReplay @unit(s) = default(10s);
        int numberOfReplays = default(1);

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
