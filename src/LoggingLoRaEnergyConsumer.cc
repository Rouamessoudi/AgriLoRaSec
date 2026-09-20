#include "LoggingLoRaEnergyConsumer.h"
#include "PacketEventLogger.h"

#include "LoRa/LoRaRadio.h"
#include "LoRa/LoRaMacFrame_m.h"
#include "LoRaPhy/LoRaPhyPreamble_m.h"
#include "inet/common/ModuleAccess.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/ITransmission.h"

namespace agrilorasec {

Define_Module(LoggingLoRaEnergyConsumer);

void LoggingLoRaEnergyConsumer::captureTxPacket(inet::Packet *pkt)
{
    txMac.clear();
    txSeq = -1;
    txBytes = pkt->getByteLength();
    txSf = -1;
    txPowerW = 0;
    txCr = -1;

    b offset = b(0);
    if (pkt->getDataLength() >= B(1) && pkt->hasAtFront<flora::LoRaPhyPreamble>()) {
        const auto &pre = pkt->peekAtFront<flora::LoRaPhyPreamble>();
        offset = pre->getChunkLength();
    }

    const flora::LoRaMacFrame *frame = nullptr;
    if (pkt->getDataLength() > offset && pkt->hasAt<flora::LoRaMacFrame>(offset)) {
        const auto &chunk = pkt->peekAt<flora::LoRaMacFrame>(offset);
        frame = chunk.get();
    }
    else if (pkt->hasAtFront<flora::LoRaMacFrame>()) {
        const auto &chunk = pkt->peekAtFront<flora::LoRaMacFrame>();
        frame = chunk.get();
    }
    if (!frame)
        return;
    txMac = frame->getTransmitterAddress().str();
    txSeq = frame->getSequenceNumber();
    txSf = frame->getLoRaSF();
    txPowerW = frame->getLoRaTP();
    txCr = frame->getLoRaCR();
}

void LoggingLoRaEnergyConsumer::receiveSignal(cComponent *source, simsignal_t signal,
        intval_t value, cObject *details)
{
    flora::LoRaEnergyConsumer::receiveSignal(source, signal, value, details);

    if (signal != inet::physicallayer::IRadio::transmissionStateChangedSignal)
        return;

    auto state = static_cast<inet::physicallayer::IRadio::TransmissionState>(value);
    auto *loraRadio = dynamic_cast<flora::LoRaRadio *>(getParentModule());

    if (state == inet::physicallayer::IRadio::TRANSMISSION_STATE_TRANSMITTING) {
        txInProgress = true;
        energyAtTxStart = totalEnergyConsumed;
        txMac.clear();
        txSeq = -1;
        txBytes = -1;
        if (loraRadio) {
            const inet::physicallayer::ITransmission *tr = loraRadio->getTransmissionInProgress();
            if (tr && tr->getPacket())
                captureTxPacket(const_cast<inet::Packet *>(tr->getPacket()));
        }
        return;
    }

    if (state == inet::physicallayer::IRadio::TRANSMISSION_STATE_IDLE && txInProgress) {
        txInProgress = false;
        double energyJ = totalEnergyConsumed - energyAtTxStart;
        cModule *loggerMod = getSimulation()->getSystemModule()->getSubmodule("packetEventLogger");
        auto *logger = loggerMod ? dynamic_cast<PacketEventLogger *>(loggerMod) : nullptr;
        cModule *host = inet::findContainingNode(this);
        if (logger)
            logger->noteTransmissionEnd(txMac, txSeq, txBytes, energyJ, txSf, txPowerW, txCr,
                    host ? host->getName() : "");
    }
}

} // namespace agrilorasec
