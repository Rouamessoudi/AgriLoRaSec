#include "LoggingPacketForwarder.h"
#include "PacketEventLogger.h"

#include "inet/common/INETMath.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/SignalTag_m.h"
#include "inet/common/ModuleAccess.h"

namespace agrilorasec {

Define_Module(LoggingPacketForwarder);

void LoggingPacketForwarder::tryLogReception(inet::Packet *pkt)
{
    // FLoRa PacketForwarder::processLoraMACPacket fait trimFront() AVANT getTag.
    // Les tags RSSI/SNIR ne sont pas toujours visibles avant ce trim.
    pkt->trimFront();
    const auto &frame = pkt->peekAtFront<flora::LoRaMacFrame>();
    if (!frame)
        return;
    if (frame->getReceiverAddress() != inet::MacAddress::BROADCAST_ADDRESS)
        return;

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
    // Journaliser AVANT le parent : processLoraMACPacket fait trimFront/removeAtFront
    if (msg->arrivedOn("lowerLayerIn")) {
        if (auto *pkt = dynamic_cast<inet::Packet *>(msg))
            tryLogReception(pkt);
    }
    flora::PacketForwarder::handleMessage(msg);
}

} // namespace agrilorasec
