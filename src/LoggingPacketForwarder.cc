#include "LoggingPacketForwarder.h"
#include "PacketEventLogger.h"

#include "inet/common/INETMath.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/SignalTag_m.h"
#include "inet/common/ModuleAccess.h"

namespace agrilorasec {

Define_Module(LoggingPacketForwarder);

void LoggingPacketForwarder::initialize(int stage)
{
    flora::PacketForwarder::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        enableDuplicateFilter = par("enableDuplicateFilter").boolValue();
        securityLogFile = par("securityLogFile").stdstringValue();
        gwPhyLogged = 0;
        gwAccepted = 0;
        gwDuplicateDetected = 0;
        gwDuplicateRejected = 0;
        seenMacSeq.clear();
        fprintf(stderr, "LoggingPacketForwarder duplicateFilter=%d log=%s\n",
                enableDuplicateFilter ? 1 : 0, securityLogFile.c_str());
        fflush(stderr);
    }
}

void LoggingPacketForwarder::finish()
{
    recordScalar("secEnableDuplicateFilter", enableDuplicateFilter ? 1 : 0);
    recordScalar("secGwPhyLogged", gwPhyLogged);
    recordScalar("secGwAccepted", gwAccepted);
    recordScalar("secGwDuplicateDetected", gwDuplicateDetected);
    recordScalar("secGwDuplicateRejected", gwDuplicateRejected);
    if (securityCsv.is_open())
        securityCsv.close();
    flora::PacketForwarder::finish();
}

void LoggingPacketForwarder::logSecurityEvent(const std::string &action, const std::string &reason,
        const std::string &mac, int seq)
{
    if (securityLogFile.empty())
        return;
    if (!securityCsv.is_open()) {
        securityCsv.open(securityLogFile.c_str(), std::ios::out | std::ios::trunc);
        if (!securityCsv)
            return;
        if (!securityHeaderWritten) {
            securityCsv << "time_s,action,reason,sender_mac,sequence_number,filter_on\n";
            securityHeaderWritten = true;
        }
    }
    securityCsv << SIMTIME_DBL(simTime()) << ","
                << action << ","
                << reason << ","
                << mac << ","
                << seq << ","
                << (enableDuplicateFilter ? 1 : 0) << "\n";
    securityCsv.flush();
}

bool LoggingPacketForwarder::isDuplicateAndRemember(const flora::LoRaMacFrame *frame)
{
    if (!frame)
        return false;
    std::string mac = frame->getTransmitterAddress().str();
    int seq = frame->getSequenceNumber();
    std::string key = mac + "#" + std::to_string(seq);
    if (seenMacSeq.count(key)) {
        gwDuplicateDetected++;
        logSecurityEvent("detect", "mac_seq_seen", mac, seq);
        return true;
    }
    seenMacSeq.insert(key);
    return false;
}

void LoggingPacketForwarder::tryLogReception(inet::Packet *pkt)
{
    // FLoRa PacketForwarder::processLoraMACPacket fait trimFront() AVANT getTag.
    pkt->trimFront();
    const auto &frame = pkt->peekAtFront<flora::LoRaMacFrame>();
    if (!frame)
        return;
    if (frame->getReceiverAddress() != inet::MacAddress::BROADCAST_ADDRESS)
        return;

    gwPhyLogged++;

    double rssiDbm = 0;
    double snir = 0;
    bool hasRssi = false;
    bool hasSnir = false;
    auto snirInd = pkt->findTag<inet::SnirInd>();
    auto signalPowerInd = pkt->findTag<inet::SignalPowerInd>();
    if (signalPowerInd) {
        double rssiMw = signalPowerInd->getPower().get() * 1000.0;
        rssiDbm = inet::math::mW2dBmW(rssiMw);
        hasRssi = true;
    }
    if (snirInd) {
        snir = snirInd->getMinimumSnir();
        hasSnir = true;
    }

    cModule *loggerMod = getSimulation()->getSystemModule()->getSubmodule("packetEventLogger");
    if (!loggerMod)
        return;
    auto *logger = dynamic_cast<PacketEventLogger *>(loggerMod);
    if (!logger)
        return;
    logger->logGatewayReception(pkt, frame.get(), hasRssi ? &rssiDbm : nullptr, hasSnir ? &snir : nullptr);
}

void LoggingPacketForwarder::handleMessage(omnetpp::cMessage *msg)
{
    if (msg->arrivedOn("lowerLayerIn")) {
        if (auto *pkt = dynamic_cast<inet::Packet *>(msg)) {
            tryLogReception(pkt);
            const auto &frame = pkt->peekAtFront<flora::LoRaMacFrame>();
            if (frame && frame->getReceiverAddress() == inet::MacAddress::BROADCAST_ADDRESS) {
                if (enableDuplicateFilter && isDuplicateAndRemember(frame.get())) {
                    gwDuplicateRejected++;
                    logSecurityEvent("reject", "duplicate_mac_seq",
                            frame->getTransmitterAddress().str(), frame->getSequenceNumber());
                    fprintf(stderr, "GW_DUP_REJECT mac=%s seq=%d t=%s\n",
                            frame->getTransmitterAddress().str().c_str(),
                            frame->getSequenceNumber(), omnetpp::simTime().str().c_str());
                    fflush(stderr);
                    delete pkt;
                    return;
                }
                if (!enableDuplicateFilter)
                    isDuplicateAndRemember(frame.get());
                gwAccepted++;
                logSecurityEvent("accept", enableDuplicateFilter ? "first_mac_seq" : "no_filter",
                        frame->getTransmitterAddress().str(), frame->getSequenceNumber());
            }
        }
    }
    flora::PacketForwarder::handleMessage(msg);
}

} // namespace agrilorasec
