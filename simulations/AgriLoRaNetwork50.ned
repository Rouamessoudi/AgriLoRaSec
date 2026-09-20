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

// AgriLoRaSec - 50 noeuds. Positions 0-19 inchangees vs 10/20. Zone display inchangee.
network AgriLoRaNetwork50
{
    parameters:
        int numberOfNodes = default(50);
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

        // ----- loRaNode0-9 : positions identiques a AgriLoRaNetwork -----
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
        // ----- loRaNode10-19 : identiques a AgriLoRaNetwork20 -----
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
        // ----- loRaNode20-29 : densification meme zone display -----
        loRaNode20: LoRaNode {
            @display("p=130,560;i=device/accesspoint");
        }
        loRaNode21: LoRaNode {
            @display("p=210,560;i=device/accesspoint");
        }
        loRaNode22: LoRaNode {
            @display("p=360,500;i=device/accesspoint");
        }
        loRaNode23: LoRaNode {
            @display("p=440,620;i=device/accesspoint");
        }
        loRaNode24: LoRaNode {
            @display("p=510,500;i=device/accesspoint");
        }
        loRaNode25: LoRaNode {
            @display("p=620,500;i=device/accesspoint");
        }
        loRaNode26: LoRaNode {
            @display("p=80,580;i=device/accesspoint");
        }
        loRaNode27: LoRaNode {
            @display("p=190,620;i=device/accesspoint");
        }
        loRaNode28: LoRaNode {
            @display("p=430,640;i=device/accesspoint");
        }
        loRaNode29: LoRaNode {
            @display("p=670,560;i=device/accesspoint");
        }
        // ----- loRaNode30-49 : densification meme zone display -----
        loRaNode30: LoRaNode {
            @display("p=115,490;i=device/accesspoint");
        }
        loRaNode31: LoRaNode {
            @display("p=195,490;i=device/accesspoint");
        }
        loRaNode32: LoRaNode {
            @display("p=275,545;i=device/accesspoint");
        }
        loRaNode33: LoRaNode {
            @display("p=355,640;i=device/accesspoint");
        }
        loRaNode34: LoRaNode {
            @display("p=415,545;i=device/accesspoint");
        }
        loRaNode35: LoRaNode {
            @display("p=495,490;i=device/accesspoint");
        }
        loRaNode36: LoRaNode {
            @display("p=575,615;i=device/accesspoint");
        }
        loRaNode37: LoRaNode {
            @display("p=635,490;i=device/accesspoint");
        }
        loRaNode38: LoRaNode {
            @display("p=705,580;i=device/accesspoint");
        }
        loRaNode39: LoRaNode {
            @display("p=245,620;i=device/accesspoint");
        }
        loRaNode40: LoRaNode {
            @display("p=155,575;i=device/accesspoint");
        }
        loRaNode41: LoRaNode {
            @display("p=235,640;i=device/accesspoint");
        }
        loRaNode42: LoRaNode {
            @display("p=305,490;i=device/accesspoint");
        }
        loRaNode43: LoRaNode {
            @display("p=345,560;i=device/accesspoint");
        }
        loRaNode44: LoRaNode {
            @display("p=425,500;i=device/accesspoint");
        }
        loRaNode45: LoRaNode {
            @display("p=505,640;i=device/accesspoint");
        }
        loRaNode46: LoRaNode {
            @display("p=585,545;i=device/accesspoint");
        }
        loRaNode47: LoRaNode {
            @display("p=655,600;i=device/accesspoint");
        }
        loRaNode48: LoRaNode {
            @display("p=735,500;i=device/accesspoint");
        }
        loRaNode49: LoRaNode {
            @display("p=85,500;i=device/accesspoint");
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
