#ifndef AGRILORASEC_PACKETEVENTLOGGER_H_
#define AGRILORASEC_PACKETEVENTLOGGER_H_

#include <omnetpp.h>
#include <fstream>
#include <map>
#include <string>

#include "inet/common/InitStages.h"
#include "inet/common/packet/Packet.h"
#include "LoRa/LoRaMacFrame_m.h"
#include <cmath>

using namespace omnetpp;
using namespace inet;

namespace agrilorasec {

class PacketEventLogger : public cSimpleModule, public cListener
{
  public:
    struct TxRecord {
        std::string mac;
        std::string senderName;
        int seq = -1;
        int64_t transmittedBytes = -1;
        double energyJ = NAN;
        int sf = -1;
        double txPowerW = 0;
        int cr = -1;
        bool used = false;
    };

    struct RxRecord {
        std::string mac;
        std::string senderName;
        int seq = -1;
        double recvTime = 0;
        double rssi = NAN;
        bool hasRssi = false;
        double snirDb = NAN;
        bool hasSnir = false;
        int64_t packetSizeB = -1;
        int sf = -1;
        double txPowerW = 0;
        int cr = -1;
        bool written = false;
    };

  protected:
    virtual void initialize(int stage) override;
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }
    virtual void finish() override;
    virtual void receiveSignal(cComponent *source, simsignal_t signalID, bool b, cObject *details) override;
    virtual void receiveSignal(cComponent *source, simsignal_t signalID, intval_t value, cObject *details) override;
    void logCollisionIfGateway(cComponent *source);

    void openCsvIfNeeded();
    void buildMacNameMap();
    std::string nameFromMac(const std::string &mac) const;
    std::string labelFromActiveConfig() const;
    std::string txKey(const std::string &mac, int seq) const;
    void tryFlushPair(const std::string &key);
    void writeRxRow(const RxRecord &rx, const TxRecord *tx);
    void writeUnreceivedTx(const TxRecord &tx);

    std::ofstream csv;
    std::string outputFile;
    long nextPacketId = 1;
    std::map<std::string, simtime_t> lastRxBySender;
    std::map<std::string, int> seqCountBySender;
    std::map<std::string, TxRecord> pendingTx;
    std::map<std::string, RxRecord> pendingRx;
    std::map<std::string, std::string> macToName;

  public:
    PacketEventLogger() {}
    virtual ~PacketEventLogger();

    void logGatewayReception(Packet *pkt, const flora::LoRaMacFrame *frame,
            const double *rssiDbm, const double *snirLinear);
    void noteTransmissionEnd(const std::string &mac, int seq, int64_t transmittedBytes,
            double energyJ, int sf, double txPowerW, int cr, const std::string &senderName);
};

} // namespace agrilorasec

#endif
