package agrilorasec;

import inet.applications.contract.IApp;

// Wormhole : capture radio reelle en A, tunnel simule, retransmission PHY en B.
simple WormholeApp like IApp
{
    parameters:
        @class(agrilorasec::WormholeApp);
        @display("i=block/erouter");
        @signal[wormholePacketSent](type=long);
        @statistic[wormholePacketSent](source=wormholePacketSent; record=count);

        string role = default("entry"); // "entry" ou "exit"
        string peerAppPath = default(""); // chemin vers WormholeApp EXIT

        volatile double timeToCapture @unit(s) = default(0s);
        volatile double tunnelDelay @unit(s) = default(uniform(0.05s, 6s));
        int numberOfForwards = default(0); // 0 = illimite (sauf file)
        int maxPendingForwards = default(4);
        double attackStart @unit(s) = default(360s);
        double attackEnd @unit(s) = default(1440s);

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
