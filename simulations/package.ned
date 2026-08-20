package agrilorasec.simulations;

import inet.node.inet.Router;
import inet.node.internetcloud.InternetCloud;
import flora.LoRaPhy.LoRaMedium;
import flora.LoraNode.LoRaNode;
import flora.LoraNode.LoRaGW;
import inet.node.inet.StandardHost;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.ethernet.Eth1G;

@license(LGPL);

// ============================================================
// AgriLoRaSec - 10 noeuds LoRa DANS la zone grise (grille 2x5)
// Chaque noeud = 3 capteurs (temperature, humidite sol, humidite air)
// ============================================================
network AgriLoRaNetwork
{
    parameters:
        int numberOfNodes = default(10);
        int numberOfGateways = default(1);
        int sensorsPerNode = default(3);
        @display("bgb=780,700");

    submodules:
        // ----- Infrastructure (haut) -----
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
        gwRouter[numberOfGateways]: Router {
            @display("p=375,200");
        }
        loRaGW[numberOfGateways]: LoRaGW {
            @display("p=375,356;is=s");
        }

        // ----- 10 noeuds : grille 2x5 DANS le cadre gris -----
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

        // Attaquant jamming (document LoRa vulnerabilities)
        jammer: LoRaNode {
            @display("p=649,194;i=device/antennatower;is=s");
        }

        // Attaquant replay
        replayer: LoRaNode {
            @display("p=648,429;i=device/antennatower;is=s");
        }

        // Attaquants wormhole (tunnel A -> B)
        wormholeA: LoRaNode {
            @display("p=100,298;i=device/antennatower;is=s");
        }
        wormholeB: LoRaNode {
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
