#ifndef AGRILORASEC_JAMMERSAFELORAMAC_H_
#define AGRILORASEC_JAMMERSAFELORAMAC_H_

#include "LoRa/LoRaMac.h"

namespace agrilorasec {

// Jammer TX-only: pas de fenetres RX Class A (elles bloquent la MAC en RECEIVING).
// Evite aussi un second sendDown pendant TRANSMIT (FSMA_Enter FLoRa).
class JammerSafeLoRaMac : public flora::LoRaMac
{
  protected:
    virtual void receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t signalID,
            omnetpp::intval_t value, omnetpp::cObject *details) override;
    virtual void handleWithFsm(omnetpp::cMessage *msg) override;
    virtual void finishCurrentTransmission() override;
    virtual void sendDataFrame(inet::Packet *frameToSend) override;

    void goIdleAfterJammerTx();

    bool sendingToRadio = false;
    bool frameOnAir = false;
};

} // namespace agrilorasec

#endif
