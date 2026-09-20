#ifndef AGRILORASEC_PRESERVEHEADERLORAMAC_H_
#define AGRILORASEC_PRESERVEHEADERLORAMAC_H_

#include "LoRa/LoRaMac.h"
#include "inet/common/packet/Packet.h"
#include "LoRa/LoRaRadio.h"

namespace agrilorasec {

// Kind interne (pas une feature ML) : trame déjà encapsulée à rejouer telle quelle.
constexpr int REPLAY_RAW_KIND = 0x5241; // 'RA'

/**
 * LoRaMac AgriLoRaSec : si le paquet porte déjà un LoRaMacFrame (replay raw),
 * n'écrase pas MAC ni sequenceNumber.
 * Uniquement sur le nœud replayer (omnetpp.ini).
 */
class PreserveHeaderLoRaMac : public flora::LoRaMac
{
  protected:
    virtual void initialize(int stage) override;
    virtual inet::Packet *encapsulate(inet::Packet *msg) override;
    virtual void sendDataFrame(inet::Packet *frameToSend) override;
    virtual void receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t signalID,
            omnetpp::intval_t value, omnetpp::cObject *details) override;

    bool sendingToRadio = false;
    bool frameOnAir = false;
    bool sawPhyTransmitting = false;
};

} // namespace agrilorasec

#endif
