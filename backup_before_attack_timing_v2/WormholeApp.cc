#include "WormholeApp.h"
#include "PreserveHeaderLoRaMac.h"
#include "AgriSensorPacket_m.h"

#include "LoRa/LoRaMacFrame_m.h"
#include "LoRaPhy/LoRaPhyPreamble_m.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadioMedium.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/ITransmission.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"
#include "inet/common/INETMath.h"

#include <cmath>
#include <cstdio>

namespace agrilorasec {

Define_Module(WormholeApp);

WormholeApp::~WormholeApp()
{
    cancelAndDelete(captureTimer);
    cancelAndDelete(tunnelTimer);
    delete capturedPacket;
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
        tunnelDelayS = par("tunnelDelay").doubleValue();
        forwardCount = 0;
        captureArmed = false;
        hasCaptured = false;
        capturedPacket = nullptr;
        capturedSeq = -1;
        capturedSample = NAN;
        capturedTemperature = NAN;
        hasAgriPayload = false;
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
            EV_INFO << "WormholeApp ENTRY: arm after " << par("timeToCapture").doubleValue()
                    << "s, tunnelDelay=" << tunnelDelayS << "s, forwards=" << numberOfForwards << "\n";
            fprintf(stderr, "WormholeApp ENTRY init tunnelDelay=%gs\n", tunnelDelayS);
            fflush(stderr);
        }
        else {
            EV_INFO << "WormholeApp EXIT started\n";
            fprintf(stderr, "WormholeApp EXIT init on %s\n", getFullPath().c_str());
            fflush(stderr);
        }
    }
}

void WormholeApp::finish()
{
    recordScalar("wormholePacketsSent", forwardCount);
    recordScalar("wormholeCapturedSeq", capturedSeq);
    recordScalar("wormholeTunnelDelayS", tunnelDelayS);
}

void WormholeApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == captureTimer) {
            captureArmed = true;
            captureTimer = nullptr;
            delete msg;
            cModule *medium = getSimulation()->getSystemModule()->getSubmodule("LoRaMedium");
            if (!medium)
                throw cRuntimeError("WormholeApp: LoRaMedium not found");
            medium->subscribe(inet::physicallayer::IRadioMedium::signalAddedSignal, this);
            EV_INFO << "WormholeApp capture ARMED at t=" << simTime() << "\n";
            fprintf(stderr, "WormholeApp capture ARMED t=%s\n", simTime().str().c_str());
            fflush(stderr);
        }
        else if (msg == tunnelTimer) {
            tunnelTimer = nullptr;
            delete msg;
            sendThroughTunnel();
        }
        else {
            delete msg;
        }
    }
    else {
        delete msg;
    }
}

void WormholeApp::receiveSignal(cComponent *source, simsignal_t signalID, cObject *obj, cObject *details)
{
    Enter_Method_Silent();
    if (role != "entry" || !captureArmed || hasCaptured || !obj)
        return;
    if (signalID != inet::physicallayer::IRadioMedium::signalAddedSignal)
        return;
    tryCaptureFromTransmission(obj);
}

void WormholeApp::logPayload(const char *prefix, Packet *pkt)
{
    if (!pkt || !pkt->hasAtFront<flora::LoRaMacFrame>())
        return;
    const auto &frame = pkt->peekAtFront<flora::LoRaMacFrame>();
    b offset = frame->getChunkLength();
    capturedSample = NAN;
    capturedTemperature = NAN;
    hasAgriPayload = false;
    if (pkt->getDataLength() > offset && pkt->hasAt<flora::LoRaAppPacket>(offset)) {
        const auto &app = pkt->peekAt<flora::LoRaAppPacket>(offset);
        capturedSample = app->getSampleMeasurement();
        EV_INFO << prefix << " LoRaAppPacket sampleMeasurement=" << capturedSample << "\n";
        offset += app->getChunkLength();
    }
    if (pkt->getDataLength() > offset && pkt->hasAt<AgriSensorPacket>(offset)) {
        const auto &agri = pkt->peekAt<AgriSensorPacket>(offset);
        capturedTemperature = agri->getTemperature();
        hasAgriPayload = true;
        EV_INFO << prefix << " AgriSensorPacket temperature=" << capturedTemperature
                << " soil=" << agri->getSoilHumidity()
                << " air=" << agri->getAirHumidity()
                << " nodeIndex=" << agri->getNodeIndex() << "\n";
        fprintf(stderr, "%s AgriSensorPacket temp=%g soil=%g air=%g nodeIndex=%d\n",
                prefix, capturedTemperature, agri->getSoilHumidity(), agri->getAirHumidity(), agri->getNodeIndex());
        fflush(stderr);
    }
}

void WormholeApp::tryCaptureFromTransmission(cObject *obj)
{
    try {
        tryCaptureFromTransmissionImpl(obj);
    }
    catch (omnetpp::cException &e) {
        EV_WARN << "WormholeApp capture skipped: " << e.what() << "\n";
        fprintf(stderr, "WormholeApp capture skipped: %s\n", e.getFormattedMessage().c_str());
        fflush(stderr);
    }
}

void WormholeApp::tryCaptureFromTransmissionImpl(cObject *obj)
{
    auto *tr = dynamic_cast<const inet::physicallayer::ITransmission *>(obj);
    if (!tr || !tr->getPacket())
        return;

    const inet::physicallayer::IRadio *radio = tr->getTransmitter();
    auto *radioMod = dynamic_cast<const cModule *>(radio);
    if (!radioMod)
        return;
    cModule *host = findContainingNode(const_cast<cModule *>(radioMod));
    if (!host)
        return;
    std::string n = host->getName();
    // Uniquement les capteurs legitimes loRaNode* (pas jammer/replayer/wormhole).
    if (n.rfind("loRaNode", 0) != 0)
        return;

    const Packet *src = tr->getPacket();
    if (src->getDataLength() < B(1) || !src->hasAtFront<flora::LoRaPhyPreamble>())
        return;
    const auto preamble = src->peekAtFront<flora::LoRaPhyPreamble>();
    b macOffset = preamble->getChunkLength();
    if (src->getDataLength() <= macOffset || !src->hasAt<flora::LoRaMacFrame>(macOffset))
        return;
    const auto macChunk = src->peekAt<flora::LoRaMacFrame>(macOffset);

    capturedMac = macChunk->getTransmitterAddress().str();
    capturedSeq = macChunk->getSequenceNumber();
    captureSimTime = simTime();

    Packet *copy = new Packet(src->getName());
    copy->insertAtBack(src->peekDataAt(macOffset, src->getDataLength() - macOffset));
    take(copy);
    delete capturedPacket;
    capturedPacket = copy;
    hasCaptured = true;
    captureArmed = false;

    EV_INFO << "WormholeApp CAPTURE from " << n
            << " mac=" << capturedMac
            << " seq=" << capturedSeq
            << " at t=" << simTime() << "\n";
    fprintf(stderr, "WormholeApp CAPTURE from %s mac=%s seq=%d t=%s tunnelDelay=%gs\n",
            n.c_str(), capturedMac.c_str(), capturedSeq, simTime().str().c_str(), tunnelDelayS);
    fflush(stderr);
    logPayload("WORMHOLE_CAPTURE", capturedPacket);

    tunnelTimer = new cMessage("tunnelTimer");
    scheduleAt(simTime() + tunnelDelayS, tunnelTimer);
}

void WormholeApp::sendThroughTunnel()
{
    if (!hasCaptured || !capturedPacket)
        return;
    if (numberOfForwards > 0 && forwardCount >= numberOfForwards)
        return;
    if (peerAppPath.empty()) {
        EV_WARN << "WormholeApp: peerAppPath empty\n";
        return;
    }
    cModule *peer = getModuleByPath(peerAppPath.c_str());
    if (!peer) {
        EV_WARN << "WormholeApp: peer not found: " << peerAppPath << "\n";
        return;
    }
    auto *exitApp = check_and_cast<WormholeApp *>(peer);
    Packet *tunneled = capturedPacket->dup();
    take(tunneled);
    EV_INFO << "WormholeApp TUNNEL A->B delay=" << tunnelDelayS
            << "s mac=" << capturedMac << " seq=" << capturedSeq
            << " at t=" << simTime() << "\n";
    fprintf(stderr, "WormholeApp TUNNEL A->B t=%s delay=%gs mac=%s seq=%d\n",
            simTime().str().c_str(), tunnelDelayS, capturedMac.c_str(), capturedSeq);
    fflush(stderr);
    exitApp->receiveFromTunnel(tunneled);
    forwardCount++;
}

void WormholeApp::receiveFromTunnel(Packet *pkt)
{
    Enter_Method("receiveFromTunnel");
    take(pkt);
    emitRawFrame(pkt);
}

void WormholeApp::emitRawFrame(Packet *pkt)
{
    if (!pkt)
        return;
    pkt->setName("WORMHOLE_RAW");
    pkt->setKind(REPLAY_RAW_KIND);

    const auto &frame = pkt->peekAtFront<flora::LoRaMacFrame>();
    tunnelSendSimTime = simTime();
    EV_INFO << "WormholeApp EXIT TX mac=" << frame->getTransmitterAddress()
            << " seq=" << frame->getSequenceNumber()
            << " at t=" << simTime() << "\n";
    fprintf(stderr, "WormholeApp EXIT TX mac=%s seq=%d t=%s (capture was t=%s, tunnelDelay=%gs)\n",
            frame->getTransmitterAddress().str().c_str(), frame->getSequenceNumber(),
            simTime().str().c_str(), captureSimTime.str().c_str(), tunnelDelayS);
    fflush(stderr);
    logPayload("WORMHOLE_EXIT", pkt);

    pkt->clearTags();
    const auto &frameForTag = pkt->peekAtFront<flora::LoRaMacFrame>();
    auto loraTag = pkt->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(frameForTag->getLoRaBW());
    loraTag->setCenterFrequency(frameForTag->getLoRaCF());
    loraTag->setSpreadFactor(frameForTag->getLoRaSF());
    loraTag->setCodeRendundance(frameForTag->getLoRaCR());
    loraTag->setUseHeader(frameForTag->getLoRaUseHeader());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    send(pkt, "socketOut");
    emit(wormholePacketSent, 1L);
}

bool WormholeApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
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
