#include "JammerApp.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"

#include <cstdio>

namespace agrilorasec {

Define_Module(JammerApp);

JammerApp::~JammerApp()
{
    cancelAndDelete(sendJamming);
    cancelAndDelete(attackStartTimer);
    cancelAndDelete(attackEndTimer);
}

void JammerApp::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == INITSTAGE_APPLICATION_LAYER) {
        bool isOperational;
        NodeStatus *nodeStatus = dynamic_cast<NodeStatus *>(findContainingNode(this)->getSubmodule("status"));
        isOperational = (!nodeStatus) || nodeStatus->getState() == NodeStatus::UP;
        if (!isOperational)
            throw cRuntimeError("This module doesn't support starting in node DOWN state");

        timeToFirstPacket = par("timeToFirstPacket");
        if (timeToFirstPacket < 0)
            timeToFirstPacket = 0;
        attackStart = par("attackStart").doubleValue();
        attackEnd = par("attackEnd").doubleValue();

        sentPackets = 0;
        numberOfPacketsToSend = par("numberOfPacketsToSend");
        awaitingPhyTxEnd = false;
        sawPhyTransmitting = false;
        jammingPacketSent = registerSignal("jammingPacketSent");

        attackStartTimer = new cMessage("attackStartTimer");
        attackEndTimer = new cMessage("attackEndTimer");
        scheduleAt(attackStart, attackStartTimer);
        scheduleAt(attackEnd, attackEndTimer);

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");
        loRaRadio->subscribe(inet::physicallayer::IRadio::transmissionStateChangedSignal, this);
        cModule *mac = getParentModule()->getSubmodule("LoRaNic")->getSubmodule("mac");
        fprintf(stderr, "JammerApp mac class=%s ned=%s radio class=%s ned=%s\n",
                mac ? mac->getClassName() : "null",
                mac ? mac->getNedTypeName() : "null",
                loRaRadio->getClassName(),
                loRaRadio->getNedTypeName());
        fflush(stderr);

        EV_INFO << "JammerApp started SF=" << getSF()
                << " (next TX after PHY end + " << floraPostTxMacWindowsS
                << "s FLoRa RX windows + timeToNextPacket)\n";
        fprintf(stderr, "JammerApp init SF=%d postTxMacWindows=%gs gap=%gs attackStart=%s attackEnd=%s\n",
                getSF(), floraPostTxMacWindowsS, par("timeToNextPacket").doubleValue(),
                attackStart.str().c_str(), attackEnd.str().c_str());
        fflush(stderr);
    }
}

void JammerApp::finish()
{
    recordScalar("jammingPacketsSent", sentPackets);
    recordScalar("jammingLastPhyAirtimeS", SIMTIME_DBL(lastPhyAirtime));
    recordScalar("jammingAttackStartS", SIMTIME_DBL(attackStart));
    recordScalar("jammingAttackEndS", SIMTIME_DBL(attackEnd));
}

void JammerApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == attackStartTimer) {
            fprintf(stderr, "JammerApp ATTACK_START t=%s\n", simTime().str().c_str());
            fflush(stderr);
            cancelAndDelete(sendJamming);
            sendJamming = new cMessage("sendJamming");
            scheduleAt(simTime() + timeToFirstPacket, sendJamming);
            return;
        }
        if (msg == attackEndTimer) {
            fprintf(stderr, "JammerApp ATTACK_END t=%s sent=%d\n", simTime().str().c_str(), sentPackets);
            fflush(stderr);
            cancelAndDelete(sendJamming);
            sendJamming = nullptr;
            return;
        }
        if (msg == sendJamming) {
            sendJamming = nullptr;
            if (inAttackWindow()) {
                sendJammingPacket();
                if (simTime() >= getSimulation()->getWarmupPeriod())
                    sentPackets++;
            }
            else {
                fprintf(stderr, "JammerApp SKIP_OUTSIDE_WINDOW t=%s\n", simTime().str().c_str());
                fflush(stderr);
            }
            delete msg;
        }
        else {
            delete msg;
        }
    }
    else {
        delete msg;
    }
}

bool JammerApp::inAttackWindow() const
{
    return simTime() >= attackStart && simTime() < attackEnd;
}

void JammerApp::receiveSignal(cComponent *source, simsignal_t signalID, intval_t value, cObject *details)
{
    Enter_Method_Silent();
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
        sawPhyTransmitting = false;
        lastPhyAirtime = simTime() - lastPhyTxStart;
        fprintf(stderr, "JammerApp PHY TX end t=%s airtime=%gs sent=%d\n",
                simTime().str().c_str(), SIMTIME_DBL(lastPhyAirtime), sentPackets);
        fflush(stderr);
        scheduleNextAfterPhyTx();
    }
}

void JammerApp::scheduleNextAfterPhyTx()
{
    if (numberOfPacketsToSend != 0 && sentPackets >= numberOfPacketsToSend)
        return;
    if (!inAttackWindow())
        return;
    double gap = par("timeToNextPacket").doubleValue();
    if (gap < 0)
        gap = 0;
    double wait = floraPostTxMacWindowsS + 0.001 + gap;
    if (simTime() + wait >= attackEnd)
        return;
    cancelAndDelete(sendJamming);
    sendJamming = new cMessage("sendJamming");
    scheduleAt(simTime() + wait, sendJamming);
    EV_INFO << "JammerApp next TX in " << wait << "s (phyAirtime=" << lastPhyAirtime
            << "s + macWindows " << floraPostTxMacWindowsS << "s + gap " << gap << "s)\n";
}

bool JammerApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
}

void JammerApp::sendJammingPacket()
{
    if (!inAttackWindow()) {
        fprintf(stderr, "JammerApp SKIP_OUTSIDE_WINDOW t=%s\n", simTime().str().c_str());
        fflush(stderr);
        return;
    }
    EV_INFO << "JAMMER SEND jamming packet #" << (sentPackets + 1) << "\n";
    fprintf(stderr, "JammerApp SEND #%d t=%s\n", sentPackets + 1, simTime().str().c_str());
    fflush(stderr);

    auto pktRequest = new Packet("JAMMING_PACKET");
    pktRequest->setKind(flora::DATA);

    auto payload = makeShared<flora::LoRaAppPacket>();
    payload->setChunkLength(B(par("dataSize").intValue()));
    payload->setMsgType(flora::DATA);
    payload->setSampleMeasurement(-1);

    auto loraTag = pktRequest->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(getBW());
    loraTag->setCenterFrequency(getCF());
    loraTag->setSpreadFactor(getSF());
    loraTag->setCodeRendundance(getCR());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    awaitingPhyTxEnd = true;
    sawPhyTransmitting = false;
    lastPhyTxStart = simTime();
    pktRequest->insertAtBack(payload);
    send(pktRequest, "socketOut");
    emit(jammingPacketSent, 1L);
}

void JammerApp::setSF(int SF) { loRaRadio->loRaSF = SF; }
int JammerApp::getSF() { return loRaRadio->loRaSF; }
void JammerApp::setTP(int TP) { loRaRadio->loRaTP = TP; }
double JammerApp::getTP() { return loRaRadio->loRaTP; }
void JammerApp::setCF(units::values::Hz CF) { loRaRadio->loRaCF = CF; }
units::values::Hz JammerApp::getCF() { return loRaRadio->loRaCF; }
void JammerApp::setBW(units::values::Hz BW) { loRaRadio->loRaBW = BW; }
units::values::Hz JammerApp::getBW() { return loRaRadio->loRaBW; }
void JammerApp::setCR(int CR) { loRaRadio->loRaCR = CR; }
int JammerApp::getCR() { return loRaRadio->loRaCR; }

} // namespace agrilorasec
