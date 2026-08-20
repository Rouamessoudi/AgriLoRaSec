package agrilorasec;

import inet.applications.contract.IApp;

// Application d'attaque : wormhole LoRa
// role = "entry" (capture) ou "exit" (reemission rapide)
simple WormholeApp like IApp
{
    parameters:
        @class(agrilorasec::WormholeApp);
        @display("i=block/erouter");
        @signal[wormholePacketSent](type=long);
        @statistic[wormholePacketSent](source=wormholePacketSent; record=count);

        string role = default("entry"); // "entry" ou "exit"
        string peerAppPath = default(""); // chemin vers l'autre WormholeApp

        volatile double timeToCapture @unit(s) = default(5s);
        int numberOfForwards = default(3);

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
