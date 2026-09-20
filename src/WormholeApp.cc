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
    captureArmed = false;
    mediumSubscribed = false;
    medium = nullptr;
    clearPending();
    cancelAndDelete(attackStartTimer);
    cancelAndDelete(attackEndTimer);
    cancelAndDelete(tunnelTimer);
    cancelAndDelete(txFreeTimer);
}

bool WormholeApp::isLegitimateSensorName(const std::string &n)
{
    return n.rfind("loRaNode", 0) == 0;
}

bool WormholeApp::inAttackWindow() const
{
    return simTime() >= attackStart && simTime() < attackEnd;
}

void WormholeApp::clearPending()
{
    for (auto &p : pending)
        delete p.pkt;
    pending.clear();
}

void WormholeApp::armCapture()
{
    if (role != "entry" || captureArmed)
        return;
    medium = getSimulation()->getSystemModule()->getSubmodule("LoRaMedium");
    if (!medium)
        throw cRuntimeError("WormholeApp: LoRaMedium not found");
    if (!mediumSubscribed) {
        medium->subscribe(inet::physicallayer::IRadioMedium::signalAddedSignal, this);
        mediumSubscribed = true;
    }
    captureArmed = true;
    fprintf(stderr, "WormholeApp ATTACK_START role=%s t=%s end=%s\n",
            role.c_str(), simTime().str().c_str(), attackEnd.str().c_str());
    fflush(stderr);
}

void WormholeApp::disarmCapture()
{
    captureArmed = false;
    if (mediumSubscribed && medium) {
        medium->unsubscribe(inet::physicallayer::IRadioMedium::signalAddedSignal, this);
        mediumSubscribed = false;
    }
    if (tunnelTimer && tunnelTimer->isScheduled())
        cancelEvent(tunnelTimer);
    if (txFreeTimer && txFreeTimer->isScheduled())
        cancelEvent(txFreeTimer);
    txBusy = false;
    awaitingPhyTxEnd = false;
    sawPhyTransmitting = false;
    clearPending();
}

void WormholeApp::scheduleTunnelTimer()
{
    if (tunnelTimer && tunnelTimer->isScheduled())
        cancelEvent(tunnelTimer);
    if (pending.empty())
        return;
    if (role == "entry" && !captureArmed)
        return;
    if (role != "entry" && radioIsTransmitting())
        return;
    simtime_t due = pending.front().due;
    if (due >= attackEnd)
        return;
    if (!tunnelTimer)
        tunnelTimer = new cMessage("tunnelTimer");
    if (due <= simTime())
        due = simTime() + SimTime(1, SIMTIME_NS);
    scheduleAt(due, tunnelTimer);
}

bool WormholeApp::radioIsTransmitting() const
{
    if (txBusy || awaitingPhyTxEnd)
        return true;
    if (!loRaRadio)
        return false;
    if (loRaRadio->getTransmissionInProgress() != nullptr)
        return true;
    return loRaRadio->getTransmissionState() == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING;
}

void WormholeApp::markTxSubmitted()
{
    txBusy = true;
    awaitingPhyTxEnd = true;
    sawPhyTransmitting = false;
    lastPhyTxStart = simTime();
}

void WormholeApp::scheduleClassAResume()
{
    if (txFreeTimer && txFreeTimer->isScheduled())
        cancelEvent(txFreeTimer);
    if (!txFreeTimer)
        txFreeTimer = new cMessage("txFreeTimer");
    scheduleAt(simTime() + kClassAWindowsS + kMacIdleMarginS, txFreeTimer);
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
        maxPendingForwards = par("maxPendingForwards");
        attackStart = par("attackStart").doubleValue();
        attackEnd = par("attackEnd").doubleValue();
        forwardCount = 0;
        captureCount = 0;
        dropQueue = 0;
        dropDup = 0;
        dropRaw = 0;
        captureArmed = false;
        wormholePacketSent = registerSignal("wormholePacketSent");

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

        attackStartTimer = new cMessage("attackStartTimer");
        attackEndTimer = new cMessage("attackEndTimer");
        scheduleAt(attackStart, attackStartTimer);
        scheduleAt(attackEnd, attackEndTimer);

        fprintf(stderr, "WormholeApp init role=%s attackStart=%s attackEnd=%s maxPending=%d\n",
                role.c_str(), attackStart.str().c_str(), attackEnd.str().c_str(), maxPendingForwards);
        fflush(stderr);
    }
}

void WormholeApp::finish()
{
    disarmCapture();
    recordScalar("wormholePacketsSent", forwardCount);
    recordScalar("wormholeCaptures", captureCount);
    recordScalar("wormholeDropQueue", dropQueue);
    recordScalar("wormholeDropDup", dropDup);
    recordScalar("wormholeDropRaw", dropRaw);
    recordScalar("wormholeAttackStartS", SIMTIME_DBL(attackStart));
    recordScalar("wormholeAttackEndS", SIMTIME_DBL(attackEnd));
}

void WormholeApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == attackStartTimer) {
            armCapture();
            return;
        }
        if (msg == attackEndTimer) {
            fprintf(stderr, "WormholeApp ATTACK_END role=%s t=%s captures=%d forwards=%d dropQ=%d dropDup=%d dropRaw=%d\n",
                    role.c_str(), simTime().str().c_str(), captureCount, forwardCount, dropQueue, dropDup, dropRaw);
            fflush(stderr);
            disarmCapture();
            return;
        }
        if (msg == tunnelTimer) {
            if (role == "entry")
                sendThroughTunnel();
            else
                sendQueuedExitTx();
            return;
        }
        if (msg == txFreeTimer) {
            txBusy = false;
            awaitingPhyTxEnd = false;
            if (role != "entry") {
                if (radioIsTransmitting()) {
                    scheduleClassAResume();
                    txBusy = true;
                    return;
                }
                fprintf(stderr, "WormholeApp CLASS_A_IDLE t=%s lastPhyAirtime=%gs\n",
                        simTime().str().c_str(), SIMTIME_DBL(lastPhyAirtime));
                fflush(stderr);
                scheduleTunnelTimer();
            }
            return;
        }
        delete msg;
    }
    else {
        delete msg;
    }
}

void WormholeApp::receiveSignal(cComponent *source, simsignal_t signalID, intval_t value, cObject *details)
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
        fprintf(stderr, "WormholeApp PHY_TX_END t=%s airtime=%gs classAWait=%gs\n",
                simTime().str().c_str(), SIMTIME_DBL(lastPhyAirtime),
                kClassAWindowsS + kMacIdleMarginS);
        fflush(stderr);
        scheduleClassAResume();
    }
}

void WormholeApp::receiveSignal(cComponent *source, simsignal_t signalID, cObject *obj, cObject *details)
{
    Enter_Method_Silent();
    if (role != "entry" || !captureArmed || !obj)
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
    if (pkt->getDataLength() > offset && pkt->hasAt<flora::LoRaAppPacket>(offset))
        offset += pkt->peekAt<flora::LoRaAppPacket>(offset)->getChunkLength();
    if (pkt->getDataLength() > offset && pkt->hasAt<AgriSensorPacket>(offset)) {
        const auto &agri = pkt->peekAt<AgriSensorPacket>(offset);
        fprintf(stderr, "%s AgriSensorPacket temp=%g soil=%g air=%g nodeIndex=%d\n",
                prefix, agri->getTemperature(), agri->getSoilHumidity(), agri->getAirHumidity(), agri->getNodeIndex());
        fflush(stderr);
    }
}

void WormholeApp::tryCaptureFromTransmission(cObject *obj)
{
    try {
        tryCaptureFromTransmissionImpl(obj);
    }
    catch (omnetpp::cException &e) {
        fprintf(stderr, "WormholeApp capture skipped: %s\n", e.getFormattedMessage().c_str());
        fflush(stderr);
    }
}

void WormholeApp::tryCaptureFromTransmissionImpl(cObject *obj)
{
    if (!inAttackWindow())
        return;
    if (numberOfForwards > 0 && forwardCount >= numberOfForwards)
        return;

    auto *tr = dynamic_cast<const inet::physicallayer::ITransmission *>(obj);
    if (!tr || !tr->getPacket())
        return;
    const Packet *src = tr->getPacket();
    if (src->getKind() == REPLAY_RAW_KIND) {
        dropRaw++;
        fprintf(stderr, "WormholeApp DROP_SELF_RAW t=%s\n", simTime().str().c_str());
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
        fprintf(stderr, "WormholeApp DROP_DUP_KEY mac=%s seq=%d t=%s\n", mac.c_str(), seq, simTime().str().c_str());
        fflush(stderr);
        return;
    }
    if ((int)pending.size() >= maxPendingForwards) {
        dropQueue++;
        fprintf(stderr, "WormholeApp DROP_QUEUE mac=%s seq=%d pending=%zu t=%s\n",
                mac.c_str(), seq, pending.size(), simTime().str().c_str());
        fflush(stderr);
        return;
    }

    Packet *copy = new Packet(src->getName());
    copy->insertAtBack(src->peekDataAt(macOffset, src->getDataLength() - macOffset));
    take(copy);
    seenKeys.insert(key);
    captureCount++;

    double delayS = par("tunnelDelay").doubleValue();
    PendingForward item;
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

    fprintf(stderr, "WormholeApp CAPTURE from %s mac=%s seq=%d t=%s delay=%gs due=%s captures=%d\n",
            n.c_str(), mac.c_str(), seq, simTime().str().c_str(), delayS,
            item.due.str().c_str(), captureCount);
    fflush(stderr);
    logPayload("WORMHOLE_CAPTURE", copy);
    scheduleTunnelTimer();
}

void WormholeApp::sendThroughTunnel()
{
    if (pending.empty())
        return;
    if (!inAttackWindow()) {
        fprintf(stderr, "WormholeApp SKIP_AFTER_END t=%s\n", simTime().str().c_str());
        fflush(stderr);
        clearPending();
        return;
    }
    if (numberOfForwards > 0 && forwardCount >= numberOfForwards) {
        clearPending();
        return;
    }

    PendingForward item = pending.front();
    pending.pop_front();
    if (simTime() < item.due) {
        pending.push_front(item);
        scheduleTunnelTimer();
        return;
    }
    if (peerAppPath.empty()) {
        delete item.pkt;
        scheduleTunnelTimer();
        return;
    }
    cModule *peer = getModuleByPath(peerAppPath.c_str());
    if (!peer) {
        fprintf(stderr, "WormholeApp peer not found: %s\n", peerAppPath.c_str());
        fflush(stderr);
        delete item.pkt;
        scheduleTunnelTimer();
        return;
    }
    auto *exitApp = check_and_cast<WormholeApp *>(peer);
    Packet *tunneled = item.pkt->dup();
    take(tunneled);
    fprintf(stderr, "WormholeApp TUNNEL A->B t=%s delay=%gs mac=%s seq=%d\n",
            simTime().str().c_str(), item.delayS, item.mac.c_str(), item.seq);
    fflush(stderr);
    exitApp->receiveFromTunnel(tunneled);
    forwardCount++;
    delete item.pkt;
    scheduleTunnelTimer();
}

void WormholeApp::receiveFromTunnel(Packet *pkt)
{
    Enter_Method("receiveFromTunnel");
    take(pkt);
    if (!inAttackWindow()) {
        fprintf(stderr, "WormholeApp EXIT DROP_AFTER_END t=%s\n", simTime().str().c_str());
        fflush(stderr);
        delete pkt;
        return;
    }
    if (radioIsTransmitting() || !pending.empty()) {
        if ((int)pending.size() >= maxPendingForwards) {
            fprintf(stderr, "WormholeApp EXIT DROP_QUEUE t=%s\n", simTime().str().c_str());
            fflush(stderr);
            delete pkt;
            return;
        }
        PendingForward item;
        item.pkt = pkt;
        item.due = simTime() + 0.15;
        pending.push_back(item);
        scheduleTunnelTimer();
        return;
    }
    emitRawFrame(pkt);
}

void WormholeApp::sendQueuedExitTx()
{
    if (pending.empty())
        return;
    if (!inAttackWindow()) {
        clearPending();
        return;
    }
    PendingForward item = pending.front();
    pending.pop_front();
    if (radioIsTransmitting()) {
        pending.push_front(item);
        return;
    }
    emitRawFrame(item.pkt);
}

void WormholeApp::emitRawFrame(Packet *pkt)
{
    if (!pkt)
        return;
    pkt->setName("WORMHOLE_RAW");
    pkt->setKind(REPLAY_RAW_KIND);

    const auto &frame = pkt->peekAtFront<flora::LoRaMacFrame>();
    fprintf(stderr, "WormholeApp EXIT TX mac=%s seq=%d t=%s\n",
            frame->getTransmitterAddress().str().c_str(), frame->getSequenceNumber(),
            simTime().str().c_str());
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

    markTxSubmitted();
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
