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

        volatile double timeToCapture @unit(s) = default(0s);
        volatile double timeToReplay @unit(s) = default(uniform(4s, 25s));
        int numberOfReplays = default(0); // 0 = illimite (sauf file)
        int maxPendingReplays = default(4);
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
