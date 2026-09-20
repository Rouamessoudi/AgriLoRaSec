#include "ReplayApp.h"
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

Define_Module(ReplayApp);

ReplayApp::~ReplayApp()
{
    cancelAndDelete(captureTimer);
    cancelAndDelete(replayTimer);
    delete capturedPacket;
}

void ReplayApp::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == INITSTAGE_APPLICATION_LAYER) {
        fprintf(stderr, "ReplayApp INITSTAGE_APPLICATION_LAYER\n");
        fflush(stderr);
        bool isOperational;
        NodeStatus *nodeStatus = dynamic_cast<NodeStatus *>(findContainingNode(this)->getSubmodule("status"));
        isOperational = (!nodeStatus) || nodeStatus->getState() == NodeStatus::UP;
        if (!isOperational)
            throw cRuntimeError("This module doesn't support starting in node DOWN state");

        numberOfReplays = par("numberOfReplays");
        replayCount = 0;
        captureArmed = false;
        hasCaptured = false;
        capturedPacket = nullptr;
        capturedSeq = -1;
        capturedSample = NAN;
        capturedTemperature = NAN;
        hasAgriPayload = false;
        replayPacketSent = registerSignal("replayPacketSent");

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");

        fprintf(stderr, "ReplayApp init: radio ok, scheduling captureTimer\n");
        fflush(stderr);
        captureTimer = new cMessage("captureTimer");
        scheduleAt(simTime() + par("timeToCapture").doubleValue(), captureTimer);

        EV_INFO << "ReplayApp: arm capture after " << par("timeToCapture").doubleValue()
                << "s, then 1 raw replay of a real loRaNode frame\n";
        fprintf(stderr, "ReplayApp init done\n");
        fflush(stderr);
    }
}

void ReplayApp::finish()
{
    recordScalar("replayPacketsSent", replayCount);
    recordScalar("replayCapturedSeq", capturedSeq);
}

void ReplayApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == captureTimer) {
            captureArmed = true;
            captureTimer = nullptr;
            delete msg;
            cModule *medium = getSimulation()->getSystemModule()->getSubmodule("LoRaMedium");
            if (!medium)
                throw cRuntimeError("ReplayApp: LoRaMedium not found");
            medium->subscribe(inet::physicallayer::IRadioMedium::signalAddedSignal, this);
            EV_INFO << "ReplayApp capture ARMED at t=" << simTime() << "\n";
            fprintf(stderr, "ReplayApp capture ARMED t=%s\n", simTime().str().c_str());
            fflush(stderr);
        }
        else if (msg == replayTimer) {
            replayTimer = nullptr;
            delete msg;
            sendReplayPacket();
        }
        else {
            delete msg;
        }
    }
    else {
        delete msg;
    }
}

void ReplayApp::receiveSignal(cComponent *source, simsignal_t signalID, cObject *obj, cObject *details)
{
    Enter_Method_Silent();
    if (!captureArmed || hasCaptured || !obj)
        return;
    if (signalID != inet::physicallayer::IRadioMedium::signalAddedSignal)
        return;
    tryCaptureFromTransmission(obj);
}

void ReplayApp::logPayload(const char *prefix, Packet *pkt)
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

void ReplayApp::tryCaptureFromTransmission(cObject *obj)
{
    try {
        tryCaptureFromTransmissionImpl(obj);
    }
    catch (omnetpp::cException &e) {
        EV_WARN << "ReplayApp capture skipped: " << e.what() << "\n";
        fprintf(stderr, "ReplayApp capture skipped: %s\n", e.getFormattedMessage().c_str());
        fflush(stderr);
    }
}

void ReplayApp::tryCaptureFromTransmissionImpl(cObject *obj)
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

    Packet *copy = new Packet(src->getName());
    copy->insertAtBack(src->peekDataAt(macOffset, src->getDataLength() - macOffset));
    take(copy);
    delete capturedPacket;
    capturedPacket = copy;
    hasCaptured = true;
    captureArmed = false;

    EV_INFO << "ReplayApp CAPTURE from " << n
            << " mac=" << capturedMac
            << " seq=" << capturedSeq
            << " at t=" << simTime() << "\n";
    fprintf(stderr, "ReplayApp CAPTURE from %s mac=%s seq=%d t=%s\n",
            n.c_str(), capturedMac.c_str(), capturedSeq, simTime().str().c_str());
    fflush(stderr);
    logPayload("CAPTURE", capturedPacket);

    replayTimer = new cMessage("replayTimer");
    scheduleAt(simTime() + par("timeToReplay").doubleValue(), replayTimer);
}

void ReplayApp::sendReplayPacket()
{
    if (!hasCaptured || !capturedPacket)
        return;
    if (numberOfReplays > 0 && replayCount >= numberOfReplays)
        return;

    auto replay = capturedPacket->dup();
    replay->setName("REPLAY_RAW");
    replay->setKind(REPLAY_RAW_KIND);

    const auto &frame = replay->peekAtFront<flora::LoRaMacFrame>();
    EV_INFO << "ReplayApp REPLAY mac=" << frame->getTransmitterAddress()
            << " seq=" << frame->getSequenceNumber()
            << " (expect same as capture " << capturedMac << " seq=" << capturedSeq << ")"
            << " at t=" << simTime() << "\n";
    fprintf(stderr, "ReplayApp REPLAY mac=%s seq=%d t=%s\n",
            frame->getTransmitterAddress().str().c_str(),
            frame->getSequenceNumber(), simTime().str().c_str());
    fflush(stderr);
    logPayload("REPLAY", replay);
    if (hasAgriPayload)
        EV_INFO << "ReplayApp payload check: temperature replayed=" << capturedTemperature
                << " (must NOT be the old dummy 25.5 unless that was the real sensor value)\n";
    else
        EV_INFO << "ReplayApp payload check: sampleMeasurement=" << capturedSample << "\n";

    replay->clearTags();
    const auto &frameForTag = replay->peekAtFront<flora::LoRaMacFrame>();
    auto loraTag = replay->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(frameForTag->getLoRaBW());
    loraTag->setCenterFrequency(frameForTag->getLoRaCF());
    loraTag->setSpreadFactor(frameForTag->getLoRaSF());
    loraTag->setCodeRendundance(frameForTag->getLoRaCR());
    loraTag->setUseHeader(frameForTag->getLoRaUseHeader());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    send(replay, "socketOut");
    emit(replayPacketSent, 1L);
    replayCount++;
}

bool ReplayApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
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
