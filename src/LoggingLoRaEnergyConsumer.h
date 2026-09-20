#ifndef AGRILORASEC_LOGGINGLORAENERGYCONSUMER_H_
#define AGRILORASEC_LOGGINGLORAENERGYCONSUMER_H_

#include "LoRaEnergyModules/LoRaEnergyConsumer.h"
#include "inet/common/packet/Packet.h"
#include <string>

namespace agrilorasec {

// Mesure energy_consumed = totalEnergyConsumed(fin TX) - totalEnergyConsumed(debut TX)
// sur LE nœud emetteur (pas le total de fin de simulation).
class LoggingLoRaEnergyConsumer : public flora::LoRaEnergyConsumer
{
  protected:
    virtual void receiveSignal(cComponent *source, simsignal_t signal, intval_t value,
            cObject *details) override;
    void captureTxPacket(inet::Packet *pkt);

    bool txInProgress = false;
    double energyAtTxStart = 0;
    std::string txMac;
    int txSeq = -1;
    int64_t txBytes = -1;
    int txSf = -1;
    double txPowerW = 0;
    int txCr = -1;
};

} // namespace agrilorasec

#endif
