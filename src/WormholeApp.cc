#include "WormholeApp.h"

namespace agrilorasec {

Define_Module(WormholeApp);

WormholeApp::~WormholeApp()
{
    cancelAndDelete(captureTimer);
    cancelAndDelete(freeRadioTimer);
}

void WormholeApp::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == INITSTAGE_APPLICATION_LAYER) {
        bool isOperational;
        NodeStatus *nodeStatus = dynamic_cast<NodeStatus *>(findContainingNode(this)->getSubmodule("status"));
        isOperational = (!nodeStatus) || nodeStatus->getState() == NodeStatus::UP;
        if (!isOperational)
            throw cRuntimeError("This module doesn't support starting in node DOWN state");

        role = par("role").stdstringValue();
        peerAppPath = par("peerAppPath").stdstringValue();
        numberOfForwards = par("numberOfForwards");
        forwardCount = 0;
        busy = false;
        wormholePacketSent = registerSignal("wormholePacketSent");

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");

        if (role == "entry") {
            captureTimer = new cMessage("captureTimer");
            scheduleAt(simTime() + par("timeToCapture").doubleValue(), captureTimer);
            EV_INFO << "WormholeApp ENTRY started\n";
        }
        else {
            EV_INFO << "WormholeApp EXIT started\n";
        }
    }
}

void WormholeApp::finish()
{
    recordScalar("wormholePacketsSent", forwardCount);
}

void WormholeApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == captureTimer) {
            doCaptureAndTunnel();
            delete msg;
            captureTimer = nullptr;

            // Attendre la fin d'emission LoRa (SF12 ~171s) avant le prochain tunnel
            if (forwardCount < numberOfForwards) {
                double wait = airTimeForSF(getSF()) + 1.0;
                captureTimer = new cMessage("captureTimer");
                scheduleAt(simTime() + wait, captureTimer);
            }
        }
        else if (msg == freeRadioTimer) {
            busy = false;
            delete msg;
            freeRadioTimer = nullptr;
            EV_INFO << "WORMHOLE EXIT radio free again\n";
        }
        else {
            delete msg;
        }
    }
    else {
        delete msg;
    }
}

bool WormholeApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
}

double WormholeApp::airTimeForSF(int sf) const
{
    if (sf == 7) return 7.808;
    if (sf == 8) return 13.9776;
    if (sf == 9) return 24.6784;
    if (sf == 10) return 49.3568;
    if (sf == 11) return 85.6064;
    return 171.2128; // SF12
}

void WormholeApp::doCaptureAndTunnel()
{
    double measurement = 25.5; // capture simulee
    EV_INFO << "WORMHOLE CAPTURE at ENTRY measurement=" << measurement << "\n";

    if (peerAppPath.empty()) {
        EV_WARN << "WORMHOLE: peerAppPath empty, cannot tunnel\n";
        return;
    }

    cModule *peer = getModuleByPath(peerAppPath.c_str());
    if (!peer) {
        EV_WARN << "WORMHOLE: peer not found: " << peerAppPath << "\n";
        return;
    }

    WormholeApp *exitApp = check_and_cast<WormholeApp *>(peer);
    EV_INFO << "WORMHOLE TUNNEL ENTRY -> EXIT (fast forward)\n";
    exitApp->receiveFromTunnel(measurement);
    forwardCount++;
}

void WormholeApp::receiveFromTunnel(double measurement)
{
    Enter_Method("receiveFromTunnel");

    if (busy) {
        EV_WARN << "WORMHOLE EXIT busy, drop tunneled packet\n";
        return;
    }

    EV_INFO << "WORMHOLE EXIT received tunneled measurement=" << measurement << "\n";
    emitWormholePacket(measurement);
}

void WormholeApp::emitWormholePacket(double measurement)
{
    EV_INFO << "WORMHOLE SEND packet #" << (forwardCount + 1)
            << " measurement=" << measurement << "\n";

    auto pktRequest = new Packet("WORMHOLE_PACKET");
    pktRequest->setKind(flora::DATA);

    auto payload = makeShared<flora::LoRaAppPacket>();
    payload->setChunkLength(B(par("dataSize").intValue()));
    payload->setMsgType(flora::DATA);
    payload->setSampleMeasurement(measurement);

    auto loraTag = pktRequest->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(getBW());
    loraTag->setCenterFrequency(getCF());
    loraTag->setSpreadFactor(getSF());
    loraTag->setCodeRendundance(getCR());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    pktRequest->insertAtBack(payload);
    send(pktRequest, "socketOut");
    emit(wormholePacketSent, 1L);
    forwardCount++;
    busy = true;

    cancelAndDelete(freeRadioTimer);
    freeRadioTimer = new cMessage("freeRadio");
    scheduleAt(simTime() + airTimeForSF(getSF()), freeRadioTimer);
}

void WormholeApp::setSF(int SF) { loRaRadio->loRaSF = SF; }
int WormholeApp::getSF() { return loRaRadio->loRaSF; }
void WormholeApp::setTP(int TP) { loRaRadio->loRaTP = TP; }
double WormholeApp::getTP() { return loRaRadio->loRaTP; }
void WormholeApp::setCF(units::values::Hz CF) { loRaRadio->loRaCF = CF; }
units::values::Hz WormholeApp::getCF() { return loRaRadio->loRaCF; }
void WormholeApp::setBW(units::values::Hz BW) { loRaRadio->loRaBW = BW; }
units::values::Hz WormholeApp::getBW() { return loRaRadio->loRaBW; }
void WormholeApp::setCR(int CR) { loRaRadio->loRaCR = CR; }
int WormholeApp::getCR() { return loRaRadio->loRaCR; }

} // namespace agrilorasec
