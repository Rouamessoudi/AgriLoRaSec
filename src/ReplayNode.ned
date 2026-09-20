package agrilorasec;

import inet.linklayer.common.WirelessInterface;
import inet.mobility.static.StationaryMobility;
import inet.networklayer.common.InterfaceTable;
import inet.applications.contract.IApp;

// Copie NED locale (pas un fork FLoRa) : LoRaNic FLoRa assigne mac.typename
// sans default(), donc omnetpp.ini ne peut pas injecter PreserveHeaderLoRaMac.
module ReplayLoRaNic extends WirelessInterface
{
    parameters:
        @display("i=block/ifcard");
        *.interfaceTableModule = default(absPath(this.interfaceTableModule));
        radio.typename = default("LoRaRadio");
        radio.antenna.mobilityModule = "^.^.^.mobility";
        radio.transmitter.typename = "LoRaTransmitter";
        radio.transmitter.headerLength = 0B;
        radio.receiver.typename = "LoRaReceiver";
        mac.typename = "agrilorasec.PreserveHeaderLoRaMac";
        queue.typename = default("DropTailQueue");
        queue.packetCapacity = default(-1);
}

module ReplayNode
{
    parameters:
        int numApps = default(0);
        string deploymentType = default("");
        double maxGatewayDistance = default(320.0);
        double gatewayX = default(320.0);
        double gatewayY = default(320.0);
        @networkNode();
        *.interfaceTableModule = default(absPath(".interfaceTable"));
        @display("bgb=297,313;i=device/accesspoint;is=vs");
    submodules:
        interfaceTable: InterfaceTable {
            @display("p=30,26");
        }
        mobility: StationaryMobility {
            @display("p=24,88");
        }
        LoRaNic: ReplayLoRaNic {
            @display("p=137,239");
        }
        app[numApps]: <> like IApp {
            parameters:
                @display("p=375,76,row,150");
        }
    connections allowunconnected:
        for i=0..numApps-1 {
            app[i].socketOut --> LoRaNic.upperLayerIn;
            LoRaNic.upperLayerOut --> app[i].socketIn;
        }
}
