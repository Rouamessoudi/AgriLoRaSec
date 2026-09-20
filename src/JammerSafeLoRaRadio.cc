#include "JammerSafeLoRaRadio.h"

#include <cstdio>

namespace agrilorasec {

Define_Module(JammerSafeLoRaRadio);

void JammerSafeLoRaRadio::handleUpperPacket(inet::Packet *packet)
{
    fprintf(stderr, "JammerSafeLoRaRadio handleUpperPacket t=%s timer=%d\n",
            omnetpp::simTime().str().c_str(),
            transmissionTimer && transmissionTimer->isScheduled() ? 1 : 0);
    fflush(stderr);
    if (transmissionTimer && transmissionTimer->isScheduled()) {
        fprintf(stderr, "JammerSafeLoRaRadio drop overlapping MAC frame t=%s\n",
                omnetpp::simTime().str().c_str());
        fflush(stderr);
        delete packet;
        return;
    }
    flora::LoRaRadio::handleUpperPacket(packet);
}

} // namespace agrilorasec
