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
    captureArmed = false;
    mediumSubscribed = false;
    medium = nullptr;
    clearPending();
    cancelAndDelete(attackStartTimer);
    cancelAndDelete(attackEndTimer);
    cancelAndDelete(replayTimer);
    cancelAndDelete(txFreeTimer);
}

bool ReplayApp::isLegitimateSensorName(const std::string &n)
{
    return n.rfind("loRaNode", 0) == 0;
}

bool ReplayApp::inAttackWindow() const
{
    return simTime() >= attackStart && simTime() < attackEnd;
}

void ReplayApp::clearPending()
{
    for (auto &p : pending)
        delete p.pkt;
    pending.clear();
}

void ReplayApp::armCapture()
{
    if (captureArmed)
        return;
    medium = getSimulation()->getSystemModule()->getSubmodule("LoRaMedium");
    if (!medium)
        throw cRuntimeError("ReplayApp: LoRaMedium not found");
    if (!mediumSubscribed) {
        medium->subscribe(inet::physicallayer::IRadioMedium::signalAddedSignal, this);
        mediumSubscribed = true;
    }
    captureArmed = true;
    EV_INFO << "ReplayApp ATTACK_START t=" << simTime() << " end=" << attackEnd << "\n";
    fprintf(stderr, "ReplayApp ATTACK_START t=%s end=%s\n",
            simTime().str().c_str(), attackEnd.str().c_str());
    fflush(stderr);
}

void ReplayApp::disarmCapture()
{
    captureArmed = false;
    if (mediumSubscribed && medium) {
        medium->unsubscribe(inet::physicallayer::IRadioMedium::signalAddedSignal, this);
        mediumSubscribed = false;
    }
    if (replayTimer && replayTimer->isScheduled())
        cancelEvent(replayTimer);
    if (txFreeTimer && txFreeTimer->isScheduled())
        cancelEvent(txFreeTimer);
    txBusy = false;
    awaitingPhyTxEnd = false;
    sawPhyTransmitting = false;
    clearPending();
}

bool ReplayApp::radioIsTransmitting() const
{
    if (txBusy || awaitingPhyTxEnd)
        return true;
    if (!loRaRadio)
        return false;
    if (loRaRadio->getTransmissionInProgress() != nullptr)
        return true;
    return loRaRadio->getTransmissionState() == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING;
}

void ReplayApp::markTxSubmitted()
{
    txBusy = true;
    awaitingPhyTxEnd = true;
    sawPhyTransmitting = false;
    lastPhyTxStart = simTime();
}

void ReplayApp::scheduleClassAResume()
{
    if (txFreeTimer && txFreeTimer->isScheduled())
        cancelEvent(txFreeTimer);
    if (!txFreeTimer)
        txFreeTimer = new cMessage("txFreeTimer");
    scheduleAt(simTime() + kClassAWindowsS + kMacIdleMarginS, txFreeTimer);
}

void ReplayApp::scheduleReplayTimer()
{
    if (replayTimer && replayTimer->isScheduled())
        cancelEvent(replayTimer);
    if (!captureArmed || pending.empty() || radioIsTransmitting())
        return;
    simtime_t due = pending.front().due;
    if (due >= attackEnd)
        return;
    if (!replayTimer)
        replayTimer = new cMessage("replayTimer");
    if (due <= simTime())
        due = simTime() + SimTime(1, SIMTIME_NS);
    scheduleAt(due, replayTimer);
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
        maxPendingReplays = par("maxPendingReplays");
        attackStart = par("attackStart").doubleValue();
        attackEnd = par("attackEnd").doubleValue();
        replayCount = 0;
        captureCount = 0;
        dropQueue = 0;
        dropDup = 0;
        dropRaw = 0;
        captureArmed = false;
        replayPacketSent = registerSignal("replayPacketSent");

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");
        loRaRadio->subscribe(inet::physicallayer::IRadio::transmissionStateChangedSignal, this);
        txBusy = false;
        awaitingPhyTxEnd = false;
        sawPhyTransmitting = false;

        fprintf(stderr, "ReplayApp init attackStart=%s attackEnd=%s maxPending=%d numberOfReplays=%d SF=%d classA=%.2fs margin=%.2fs\n",
                attackStart.str().c_str(), attackEnd.str().c_str(), maxPendingReplays, numberOfReplays,
                (int)par("initialLoRaSF"), kClassAWindowsS, kMacIdleMarginS);
        fflush(stderr);

        attackStartTimer = new cMessage("attackStartTimer");
        attackEndTimer = new cMessage("attackEndTimer");
        scheduleAt(attackStart, attackStartTimer);
        scheduleAt(attackEnd, attackEndTimer);
    }
}

void ReplayApp::finish()
{
    disarmCapture();
    recordScalar("replayPacketsSent", replayCount);
    recordScalar("replayCaptures", captureCount);
    recordScalar("replayDropQueue", dropQueue);
    recordScalar("replayDropDup", dropDup);
    recordScalar("replayDropRaw", dropRaw);
    recordScalar("replayAttackStartS", SIMTIME_DBL(attackStart));
    recordScalar("replayAttackEndS", SIMTIME_DBL(attackEnd));
}

void ReplayApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == attackStartTimer) {
            armCapture();
            return;
        }
        if (msg == attackEndTimer) {
            fprintf(stderr, "ReplayApp ATTACK_END t=%s captures=%d replays=%d dropQ=%d dropDup=%d dropRaw=%d\n",
                    simTime().str().c_str(), captureCount, replayCount, dropQueue, dropDup, dropRaw);
            fflush(stderr);
            disarmCapture();
            return;
        }
        if (msg == replayTimer) {
            sendReplayPacket();
            return;
        }
        if (msg == txFreeTimer) {
            txBusy = false;
            awaitingPhyTxEnd = false;
            if (radioIsTransmitting()) {
                fprintf(stderr, "ReplayApp CLASS_A_RESUME still busy t=%s\n", simTime().str().c_str());
                fflush(stderr);
                scheduleClassAResume();
                txBusy = true;
                return;
            }
            fprintf(stderr, "ReplayApp CLASS_A_IDLE t=%s lastPhyAirtime=%gs\n",
                    simTime().str().c_str(), SIMTIME_DBL(lastPhyAirtime));
            fflush(stderr);
            scheduleReplayTimer();
            return;
        }
        delete msg;
    }
    else {
        delete msg;
    }
}

void ReplayApp::receiveSignal(cComponent *source, simsignal_t signalID, intval_t value, cObject *details)
{
    Enter_Method_Silent();
    (void)source;
    (void)details;
    if (signalID != inet::physicallayer::IRadio::transmissionStateChangedSignal)
        return;
    auto state = static_cast<inet::physicallayer::IRadio::TransmissionState>(value);
    if (state == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING && awaitingPhyTxEnd) {
        sawPhyTransmitting = true;
        lastPhyTxStart = simTime();
        return;
    }
    if (state == inet::physicallayer::IRadio::TRANSMISSION_STATE_IDLE && awaitingPhyTxEnd && sawPhyTransmitting) {
        awaitingPhyTxEnd = false;
        lastPhyAirtime = simTime() - lastPhyTxStart;
        fprintf(stderr, "ReplayApp PHY_TX_END t=%s airtime=%gs classAWait=%gs\n",
                simTime().str().c_str(), SIMTIME_DBL(lastPhyAirtime),
                kClassAWindowsS + kMacIdleMarginS);
        fflush(stderr);
        scheduleClassAResume();
    }
}

void ReplayApp::receiveSignal(cComponent *source, simsignal_t signalID, cObject *obj, cObject *details)
{
    Enter_Method_Silent();
    if (!captureArmed || !obj)
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
    if (pkt->getDataLength() > offset && pkt->hasAt<flora::LoRaAppPacket>(offset)) {
        const auto &app = pkt->peekAt<flora::LoRaAppPacket>(offset);
        EV_INFO << prefix << " LoRaAppPacket sampleMeasurement=" << app->getSampleMeasurement() << "\n";
        offset += app->getChunkLength();
    }
    if (pkt->getDataLength() > offset && pkt->hasAt<AgriSensorPacket>(offset)) {
        const auto &agri = pkt->peekAt<AgriSensorPacket>(offset);
        fprintf(stderr, "%s AgriSensorPacket temp=%g soil=%g air=%g nodeIndex=%d\n",
                prefix, agri->getTemperature(), agri->getSoilHumidity(), agri->getAirHumidity(), agri->getNodeIndex());
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
    if (!inAttackWindow())
        return;
    if (numberOfReplays > 0 && replayCount >= numberOfReplays)
        return;

    auto *tr = dynamic_cast<const inet::physicallayer::ITransmission *>(obj);
    if (!tr || !tr->getPacket())
        return;

    const Packet *src = tr->getPacket();
    if (src->getKind() == REPLAY_RAW_KIND) {
        dropRaw++;
        fprintf(stderr, "ReplayApp DROP_SELF_RAW t=%s\n", simTime().str().c_str());
        fflush(stderr);
        return;
    }

    const inet::physicallayer::IRadio *radio = tr->getTransmitter();
    auto *radioMod = dynamic_cast<const cModule *>(radio);
    if (!radioMod)
        return;
    cModule *host = findContainingNode(const_cast<cModule *>(radioMod));
    if (!host)
        return;
    std::string n = host->getName();
    if (!isLegitimateSensorName(n))
        return;

    if (src->getDataLength() < B(1) || !src->hasAtFront<flora::LoRaPhyPreamble>())
        return;
    const auto preamble = src->peekAtFront<flora::LoRaPhyPreamble>();
    b macOffset = preamble->getChunkLength();
    if (src->getDataLength() <= macOffset || !src->hasAt<flora::LoRaMacFrame>(macOffset))
        return;
    const auto macChunk = src->peekAt<flora::LoRaMacFrame>(macOffset);

    std::string mac = macChunk->getTransmitterAddress().str();
    int seq = macChunk->getSequenceNumber();
    std::string key = mac + "#" + std::to_string(seq);
    if (seenKeys.count(key)) {
        dropDup++;
        fprintf(stderr, "ReplayApp DROP_DUP_KEY mac=%s seq=%d t=%s\n", mac.c_str(), seq, simTime().str().c_str());
        fflush(stderr);
        return;
    }
    if ((int)pending.size() >= maxPendingReplays) {
        dropQueue++;
        fprintf(stderr, "ReplayApp DROP_QUEUE mac=%s seq=%d pending=%zu t=%s\n",
                mac.c_str(), seq, pending.size(), simTime().str().c_str());
        fflush(stderr);
        return;
    }

    Packet *copy = new Packet(src->getName());
    copy->insertAtBack(src->peekDataAt(macOffset, src->getDataLength() - macOffset));
    take(copy);
    seenKeys.insert(key);
    captureCount++;

    double delayS = par("timeToReplay").doubleValue();
    PendingReplay item;
    item.pkt = copy;
    item.mac = mac;
    item.seq = seq;
    item.captureTime = simTime();
    item.delayS = delayS;
    item.due = simTime() + delayS;
    auto it = pending.begin();
    while (it != pending.end() && it->due <= item.due)
        ++it;
    pending.insert(it, item);

    EV_INFO << "ReplayApp CAPTURE from " << n << " mac=" << mac << " seq=" << seq
            << " at t=" << simTime() << " delay=" << delayS << "s\n";
    fprintf(stderr, "ReplayApp CAPTURE from %s mac=%s seq=%d t=%s delay=%gs due=%s captures=%d\n",
            n.c_str(), mac.c_str(), seq, simTime().str().c_str(), delayS,
            item.due.str().c_str(), captureCount);
    fflush(stderr);
    logPayload("CAPTURE", copy);
    scheduleReplayTimer();
}

void ReplayApp::sendReplayPacket()
{
    if (pending.empty())
        return;
    if (!inAttackWindow()) {
        fprintf(stderr, "ReplayApp SKIP_AFTER_END t=%s\n", simTime().str().c_str());
        fflush(stderr);
        clearPending();
        return;
    }
    if (numberOfReplays > 0 && replayCount >= numberOfReplays) {
        clearPending();
        return;
    }

    PendingReplay item = pending.front();
    pending.pop_front();
    if (simTime() < item.due) {
        pending.push_front(item);
        scheduleReplayTimer();
        return;
    }
    if (radioIsTransmitting()) {
        pending.push_front(item);
        return;
    }

    auto replay = item.pkt->dup();
    replay->setName("REPLAY_RAW");
    replay->setKind(REPLAY_RAW_KIND);

    const auto &frame = replay->peekAtFront<flora::LoRaMacFrame>();
    fprintf(stderr, "ReplayApp REPLAY mac=%s seq=%d t=%s capture_t=%s delay=%gs\n",
            frame->getTransmitterAddress().str().c_str(), frame->getSequenceNumber(),
            simTime().str().c_str(), item.captureTime.str().c_str(), item.delayS);
    fflush(stderr);
    logPayload("REPLAY", replay);

    replay->clearTags();
    const auto &frameForTag = replay->peekAtFront<flora::LoRaMacFrame>();
    auto loraTag = replay->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(frameForTag->getLoRaBW());
    loraTag->setCenterFrequency(frameForTag->getLoRaCF());
    loraTag->setSpreadFactor(frameForTag->getLoRaSF());
    loraTag->setCodeRendundance(frameForTag->getLoRaCR());
    loraTag->setUseHeader(frameForTag->getLoRaUseHeader());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    markTxSubmitted();
    send(replay, "socketOut");
    emit(replayPacketSent, 1L);
    replayCount++;
    delete item.pkt;
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
