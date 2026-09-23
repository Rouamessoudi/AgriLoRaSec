#ifndef AGRILORASEC_LOGGINGPACKETFORWARDER_H_
#define AGRILORASEC_LOGGINGPACKETFORWARDER_H_

#include "LoRa/PacketForwarder.h"
#include "inet/common/packet/Packet.h"
#include "LoRa/LoRaMacFrame_m.h"

#include <fstream>
#include <set>
#include <string>

namespace agrilorasec {

class LoggingPacketForwarder : public flora::PacketForwarder
{
  protected:
    virtual void initialize(int stage) override;
    virtual void finish() override;
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    void tryLogReception(inet::Packet *pkt);
    bool isDuplicateAndRemember(const flora::LoRaMacFrame *frame);
    void logSecurityEvent(const std::string &action, const std::string &reason,
            const std::string &mac, int seq);

    bool enableDuplicateFilter = false;
    std::set<std::string> seenMacSeq;
    long gwPhyLogged = 0;
    long gwAccepted = 0;
    long gwDuplicateDetected = 0;
    long gwDuplicateRejected = 0;
    std::string securityLogFile;
    std::ofstream securityCsv;
    bool securityHeaderWritten = false;
};

} // namespace agrilorasec

#endif
