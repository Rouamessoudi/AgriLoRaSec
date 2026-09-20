#ifndef AGRILORASEC_LOGGINGPACKETFORWARDER_H_
#define AGRILORASEC_LOGGINGPACKETFORWARDER_H_

#include "LoRa/PacketForwarder.h"
#include "inet/common/packet/Packet.h"
#include "LoRa/LoRaMacFrame_m.h"

namespace agrilorasec {

class LoggingPacketForwarder : public flora::PacketForwarder
{
  protected:
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    void tryLogReception(inet::Packet *pkt);
};

} // namespace agrilorasec

#endif
