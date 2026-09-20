package agrilorasec.simulations;

import inet.node.inet.Router;
import inet.node.internetcloud.InternetCloud;
import flora.LoRaPhy.LoRaMedium;
import flora.LoraNode.LoRaNode;
import agrilorasec.ReplayNode;
import agrilorasec.WormholeExitNode;
import agrilorasec.JammerNode;
import agrilorasec.PacketEventLogger;
import agrilorasec.AgriLoRaGW;
import inet.node.inet.StandardHost;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.ethernet.Eth1G;

@license(LGPL);

// ============================================================
// AgriLoRaSec - 20 noeuds LoRa (scalabilite). Reseau SEPARÉ du 10 noeuds.
// Positions 0-9 identiques à AgriLoRaNetwork ; 10-19 ajoutes dans la zone.
// ============================================================
network AgriLoRaNetwork20
{
    parameters:
        int numberOfNodes = default(20);
        int numberOfGateways = default(1);
        int sensorsPerNode = default(3);
        @display("bgb=780,700");

    submodules:
        networkServer: StandardHost {
            @display("p=70,60");
        }
        configurator: Ipv4NetworkConfigurator {
            assignDisjunctSubnetAddresses = false;
            @display("p=303,30");
        }
        nsRouter: Router {
            @display("p=200,59");
        }
        internetCloud: InternetCloud {
            @display("p=414,58");
        }
        LoRaMedium: LoRaMedium {
            @display("p=650,80");
        }
        packetEventLogger: PacketEventLogger {
            @display("p=520,30;i=block/table");
        }
        gwRouter[numberOfGateways]: Router {
            @display("p=375,200");
        }
        loRaGW[numberOfGateways]: AgriLoRaGW {
            @display("p=375,356;is=s");
        }

        // ----- 10 premiers noeuds : memes positions que AgriLoRaNetwork -----
        loRaNode0: LoRaNode {
            @display("p=100,534;i=device/accesspoint");
        }
        loRaNode1: LoRaNode {
            @display("p=90,462;i=device/accesspoint");
        }
        loRaNode2: LoRaNode {
            @display("p=69,634;i=device/accesspoint");
        }
        loRaNode3: LoRaNode {
            @display("p=320,534;i=device/accesspoint");
        }
        loRaNode4: LoRaNode {
            @display("p=541,534;i=device/accesspoint");
        }
        loRaNode5: LoRaNode {
            @display("p=320,615;i=device/accesspoint");
        }
        loRaNode6: LoRaNode {
            @display("p=217,634;i=device/accesspoint");
        }
        loRaNode7: LoRaNode {
            @display("p=648,634;i=device/accesspoint");
        }
        loRaNode8: LoRaNode {
            @display("p=482,600;i=device/accesspoint");
        }
        loRaNode9: LoRaNode {
            @display("p=698,518;i=device/accesspoint");
        }

        // ----- 10 noeuds ajoutes (scalabilite 20) -----
        loRaNode10: LoRaNode {
            @display("p=175,500;i=device/accesspoint");
        }
        loRaNode11: LoRaNode {
            @display("p=250,500;i=device/accesspoint");
        }
        loRaNode12: LoRaNode {
            @display("p=400,470;i=device/accesspoint");
        }
        loRaNode13: LoRaNode {
            @display("p=470,534;i=device/accesspoint");
        }
        loRaNode14: LoRaNode {
            @display("p=590,560;i=device/accesspoint");
        }
        loRaNode15: LoRaNode {
            @display("p=150,650;i=device/accesspoint");
        }
        loRaNode16: LoRaNode {
            @display("p=390,580;i=device/accesspoint");
        }
        loRaNode17: LoRaNode {
            @display("p=560,470;i=device/accesspoint");
        }
        loRaNode18: LoRaNode {
            @display("p=720,630;i=device/accesspoint");
        }
        loRaNode19: LoRaNode {
            @display("p=280,470;i=device/accesspoint");
        }

        jammer: JammerNode {
            @display("p=649,194;i=device/antennatower;is=s");
        }
        replayer: ReplayNode {
            @display("p=648,429;i=device/antennatower;is=s");
        }
        wormholeA: LoRaNode {
            @display("p=100,298;i=device/antennatower;is=s");
        }
        wormholeB: WormholeExitNode {
            @display("p=649,311;i=device/antennatower;is=s");
        }

    connections:
        networkServer.ethg++ <--> Eth1G <--> nsRouter.ethg++;
        nsRouter.pppg++ <--> Eth1G <--> internetCloud.pppg++;
        for i=0..numberOfGateways-1 {
            internetCloud.pppg++ <--> Eth1G <--> gwRouter[i].pppg++;
            gwRouter[i].ethg++ <--> Eth1G <--> loRaGW[i].ethg++;
        }
}
