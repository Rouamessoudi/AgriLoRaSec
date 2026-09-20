#include "PreserveHeaderLoRaMac.h"
#include "LoRa/LoRaMacFrame_m.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"
#include <cstdio>

namespace agrilorasec {

Define_Module(PreserveHeaderLoRaMac);

void PreserveHeaderLoRaMac::initialize(int stage)
{
    flora::LoRaMac::initialize(stage);
    if (stage == 0) {
        fprintf(stderr, "PreserveHeaderLoRaMac initialized on %s\n", getFullPath().c_str());
        fflush(stderr);
    }
}

inet::Packet *PreserveHeaderLoRaMac::encapsulate(inet::Packet *msg)
{
    if (msg->getKind() == REPLAY_RAW_KIND && msg->hasAtFront<flora::LoRaMacFrame>()) {
        const auto &frame = msg->peekAtFront<flora::LoRaMacFrame>();
        EV_INFO << "PreserveHeaderLoRaMac skip encapsulate mac="
                << frame->getTransmitterAddress()
                << " seq=" << frame->getSequenceNumber() << "\n";
        fprintf(stderr, "PreserveHeaderLoRaMac skip encapsulate mac=%s seq=%d\n",
                frame->getTransmitterAddress().str().c_str(), frame->getSequenceNumber());
        fflush(stderr);
        return msg;
    }
    return flora::LoRaMac::encapsulate(msg);
}

void PreserveHeaderLoRaMac::sendDataFrame(inet::Packet *frameToSend)
{
    // FLoRa FSMA_Enter(TRANSMIT) can sendDown twice (mode switch / nested signals).
    if (sendingToRadio || frameOnAir)
        return;
    if (radio && radio->getTransmissionState() == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING)
        return;
    auto *lora = dynamic_cast<flora::LoRaRadio *>(radio);
    if (lora && lora->getTransmissionInProgress() != nullptr)
        return;
    sendingToRadio = true;
    frameOnAir = true;
    sawPhyTransmitting = false;
    flora::LoRaMac::sendDataFrame(frameToSend);
    sendingToRadio = false;
}

void PreserveHeaderLoRaMac::receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t signalID,
        omnetpp::intval_t value, omnetpp::cObject *details)
{
    flora::LoRaMac::receiveSignal(source, signalID, value, details);
    if (signalID != inet::physicallayer::IRadio::transmissionStateChangedSignal)
        return;
    auto state = static_cast<inet::physicallayer::IRadio::TransmissionState>(value);
    if (state == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING && frameOnAir)
        sawPhyTransmitting = true;
    if (state == inet::physicallayer::IRadio::TRANSMISSION_STATE_IDLE && frameOnAir && sawPhyTransmitting) {
        frameOnAir = false;
        sawPhyTransmitting = false;
    }
}

} // namespace agrilorasec
