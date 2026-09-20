#include "JammerSafeLoRaMac.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"
#include "LoRa/LoRaRadio.h"

namespace agrilorasec {

Define_Module(JammerSafeLoRaMac);

void JammerSafeLoRaMac::goIdleAfterJammerTx()
{
    if (endDelay_1) cancelEvent(endDelay_1);
    if (endListening_1) cancelEvent(endListening_1);
    if (endDelay_2) cancelEvent(endDelay_2);
    if (endListening_2) cancelEvent(endListening_2);
    fsm.setState(IDLE);
    turnOffReceiver();
    frameOnAir = false;
}

void JammerSafeLoRaMac::finishCurrentTransmission()
{
    deleteCurrentTxFrame();
    goIdleAfterJammerTx();
}

void JammerSafeLoRaMac::handleWithFsm(omnetpp::cMessage *msg)
{
    flora::LoRaMac::handleWithFsm(msg);
    int st = fsm.getState();
    if (st == WAIT_DELAY_1 || st == LISTENING_1 || st == RECEIVING_1
            || st == WAIT_DELAY_2 || st == LISTENING_2 || st == RECEIVING_2) {
        goIdleAfterJammerTx();
        if (currentTxFrame == nullptr && txQueue && !txQueue->isEmpty())
            processUpperPacket();
    }
}

void JammerSafeLoRaMac::receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t signalID,
        omnetpp::intval_t value, omnetpp::cObject *details)
{
    flora::LoRaMac::receiveSignal(source, signalID, value, details);
    if (signalID == inet::physicallayer::IRadio::transmissionStateChangedSignal
            && !sendingToRadio
            && radio
            && radio->getTransmissionState() == inet::physicallayer::IRadio::TRANSMISSION_STATE_IDLE)
        frameOnAir = false;
}

void JammerSafeLoRaMac::sendDataFrame(inet::Packet *frameToSend)
{
    if (sendingToRadio || frameOnAir)
        return;
    if (radio && radio->getTransmissionState() == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING)
        return;
    auto *lora = dynamic_cast<flora::LoRaRadio *>(radio);
    if (lora && lora->getTransmissionInProgress() != nullptr)
        return;

    sendingToRadio = true;
    frameOnAir = true;
    fprintf(stderr, "JammerSafeLoRaMac sendDataFrame t=%s\n", omnetpp::simTime().str().c_str());
    fflush(stderr);
    flora::LoRaMac::sendDataFrame(frameToSend);
    sendingToRadio = false;
}

} // namespace agrilorasec
