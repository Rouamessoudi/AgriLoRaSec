#include "ReplayApp.h"

namespace agrilorasec {

Define_Module(ReplayApp);

ReplayApp::~ReplayApp()
{
    cancelAndDelete(captureTimer);
    cancelAndDelete(replayTimer);
}

void ReplayApp::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == INITSTAGE_APPLICATION_LAYER) {
        bool isOperational;
        NodeStatus *nodeStatus = dynamic_cast<NodeStatus *>(findContainingNode(this)->getSubmodule("status"));
        isOperational = (!nodeStatus) || nodeStatus->getState() == NodeStatus::UP;
        if (!isOperational)
            throw cRuntimeError("This module doesn't support starting in node DOWN state");

        numberOfReplays = par("numberOfReplays");
        replayCount = 0;
        hasCaptured = false;
        replayPacketSent = registerSignal("replayPacketSent");

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");

        captureTimer = new cMessage("captureTimer");
        scheduleAt(simTime() + par("timeToCapture").doubleValue(), captureTimer);

        EV_INFO << "ReplayApp started: will simulate capture then replay\n";
    }
}

void ReplayApp::finish()
{
    recordScalar("replayPacketsSent", replayCount);
}

void ReplayApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == captureTimer) {
            doCapture();
            delete msg;
            captureTimer = nullptr;

            replayTimer = new cMessage("replayTimer");
            scheduleAt(simTime() + par("timeToReplay").doubleValue(), replayTimer);
        }
        else if (msg == replayTimer) {
            sendReplayPacket();
            delete msg;
            replayTimer = nullptr;

            if (replayCount < numberOfReplays) {
                replayTimer = new cMessage("replayTimer");
                scheduleAt(simTime() + par("timeToReplay").doubleValue(), replayTimer);
            }
        }
    }
    else {
        delete msg;
    }
}

bool ReplayApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
}

void ReplayApp::doCapture()
{
    // Simulation pedagogique d'une capture d'une mesure legitime
    capturedMeasurement = 25.5;
    hasCaptured = true;
    EV_INFO << "REPLAY CAPTURE simulated measurement=" << capturedMeasurement << "\n";
}

void ReplayApp::sendReplayPacket()
{
    if (!hasCaptured)
        return;

    EV_INFO << "REPLAY SEND packet #" << (replayCount + 1)
            << " measurement=" << capturedMeasurement << "\n";

    auto pktRequest = new Packet("REPLAY_PACKET");
    pktRequest->setKind(flora::DATA);

    auto payload = makeShared<flora::LoRaAppPacket>();
    payload->setChunkLength(B(par("dataSize").intValue()));
    payload->setMsgType(flora::DATA);
    payload->setSampleMeasurement(capturedMeasurement);

    auto loraTag = pktRequest->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(getBW());
    loraTag->setCenterFrequency(getCF());
    loraTag->setSpreadFactor(getSF());
    loraTag->setCodeRendundance(getCR());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    pktRequest->insertAtBack(payload);
    send(pktRequest, "socketOut");
    emit(replayPacketSent, 1L);
    replayCount++;
}

void ReplayApp::setSF(int SF) { loRaRadio->loRaSF = SF; }
int ReplayApp::getSF() { return loRaRadio->loRaSF; }
void ReplayApp::setTP(int TP) { loRaRadio->loRaTP = TP; }
double ReplayApp::getTP() { return loRaRadio->loRaTP; }
void ReplayApp::setCF(units::values::Hz CF) { loRaRadio->loRaCF = CF; }
units::values::Hz ReplayApp::getCF() { return loRaRadio->loRaCF; }
void ReplayApp::setBW(units::values::Hz BW) { loRaRadio->loRaBW = BW; }
units::values::Hz ReplayApp::getBW() { return loRaRadio->loRaBW; }
void ReplayApp::setCR(int CR) { loRaRadio->loRaCR = CR; }
int ReplayApp::getCR() { return loRaRadio->loRaCR; }

} // namespace agrilorasec
