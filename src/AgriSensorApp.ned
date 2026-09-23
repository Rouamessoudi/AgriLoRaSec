package agrilorasec;

import inet.applications.contract.IApp;

// Application PFE : chaque noeud envoie 3 mesures agricoles
// - temperature
// - humidite du sol
// - humidite de l'air
simple AgriSensorApp like IApp
{
    parameters:
        @class(agrilorasec::AgriSensorApp);
        @display("i=block/app");
        @signal[LoRa_AppPacketSent](type=long);
        @statistic[LoRa_AppPacketSent](source=LoRa_AppPacketSent; record=count);
        @signal[temperatureSent](type=double);
        @signal[soilHumiditySent](type=double);
        @signal[airHumiditySent](type=double);
        @statistic[temperatureSent](source=temperatureSent; record=vector,stats);
        @statistic[soilHumiditySent](source=soilHumiditySent; record=vector,stats);
        @statistic[airHumiditySent](source=airHumiditySent; record=vector,stats);

        int numberOfPacketsToSend = default(0);
        volatile double timeToFirstPacket @unit(s) = default(10s);
        volatile double timeToNextPacket @unit(s) = default(10s);

        // Plages des 3 capteurs agricoles
        double minTemperature = default(10);
        double maxTemperature = default(40);
        double minSoilHumidity = default(10);
        double maxSoilHumidity = default(90);
        double minAirHumidity = default(20);
        double maxAirHumidity = default(95);

        // Parametres radio LoRa (comme SimpleLoRaApp)
        double initialLoRaTP @unit(dBm) = default(14dBm);
        double initialLoRaCF @unit(Hz) = default(868MHz);
        int initialLoRaSF = default(12);
        double initialLoRaBW @unit(Hz) = default(125kHz);
        int initialLoRaCR = default(4);
        bool initialUseHeader = default(true);
        bool evaluateADRinNode = default(false);
        int dataSize @unit(B) = default(20B);

        // Mitigation jamming : hop de frequence (FLoRa ne collisionne que si meme loRaCF).
        // Desactive par defaut : les campagnes V2/V3 restent inchangees.
        bool enableChannelHop = default(false);
        double channelHopTime @unit(s) = default(360s);
        double channelHopFrequency @unit(Hz) = default(868.3MHz);

    gates:
        input socketIn @labels(LoRaAppPacket/up);
        output socketOut @labels(LoRaAppPacket/down);
}
