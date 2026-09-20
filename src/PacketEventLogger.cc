#include "PacketEventLogger.h"

#include "inet/common/INETMath.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/SignalTag_m.h"

#include <cmath>

namespace agrilorasec {

Define_Module(PacketEventLogger);

PacketEventLogger::~PacketEventLogger()
{
    if (csv.is_open())
        csv.close();
}

void PacketEventLogger::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == 0) {
        outputFile = par("outputFile").stdstringValue();
        nextPacketId = 1;
        lastRxBySender.clear();
        seqCountBySender.clear();
        pendingTx.clear();
        pendingRx.clear();
        getSimulation()->getSystemModule()->subscribe("LoRaReceptionCollision", this);
    }
    else if (stage == INITSTAGE_APPLICATION_LAYER) {
        buildMacNameMap();
    }
}

void PacketEventLogger::openCsvIfNeeded()
{
    if (csv.is_open())
        return;
    csv.open(outputFile.c_str(), std::ios::out | std::ios::trunc);
    if (!csv)
        throw cRuntimeError("PacketEventLogger: cannot open %s", outputFile.c_str());
    // packet_size_B = octets du paquet RECU a la GW (pas de colonne received_bytes redondante)
    // transmitted_bytes = getByteLength() a l'emission radio
    // energy_consumed = delta LoRaEnergyConsumer pendant CETTE TX (J)
    csv << "packet_id,recv_time_s,sender_mac,sender_name,receiver_id,rssi_dBm,snir_dB,packet_size_B,"
        << "transmitted_bytes,energy_consumed,sequence_number,spreading_factor,tx_power_dBm,"
        << "coding_rate,seq_seen_before,interarrival_s,collision,received,Label\n";
}

std::string PacketEventLogger::labelFromActiveConfig() const
{
    cConfigurationEx *cfg = getEnvir()->getConfigEx();
    const char *name = cfg ? cfg->getVariable(CFGVAR_CONFIGNAME) : nullptr;
    std::string c = name ? name : "NoAttack";
    if (c.find("Jamming") != std::string::npos)
        return "Jamming";
    if (c.find("Replay") != std::string::npos)
        return "Replay";
    if (c.find("Wormhole") != std::string::npos)
        return "Wormhole";
    return "Normal";
}

void PacketEventLogger::buildMacNameMap()
{
    cModule *net = getSimulation()->getSystemModule();
    for (cModule::SubmoduleIterator it(net); !it.end(); ++it) {
        cModule *mod = *it;
        cModule *nic = mod->getSubmodule("LoRaNic");
        if (!nic)
            continue;
        cModule *macMod = nic->getSubmodule("mac");
        if (!macMod || !macMod->hasPar("address"))
            continue;
        std::string addr = macMod->par("address").stdstringValue();
        if (!addr.empty() && addr != "auto")
            macToName[addr] = mod->getName();
    }
}

std::string PacketEventLogger::nameFromMac(const std::string &mac) const
{
    if (mac.empty())
        return "";
    auto it = macToName.find(mac);
    if (it == macToName.end())
        return "";
    return it->second;
}

std::string PacketEventLogger::txKey(const std::string &mac, int seq) const
{
    return mac + ":" + std::to_string(seq);
}

void PacketEventLogger::writeRxRow(const RxRecord &rx, const TxRecord *tx)
{
    openCsvIfNeeded();
    int seq = rx.seq;
    int seqSeenBefore = 0;
    if (!rx.mac.empty() && seq >= 0) {
        std::string seqKey = txKey(rx.mac, seq);
        auto seqIt = seqCountBySender.find(seqKey);
        if (seqIt != seqCountBySender.end() && seqIt->second > 0)
            seqSeenBefore = 1;
        seqCountBySender[seqKey] += 1;
    }

    csv << nextPacketId++ << ","
        << rx.recvTime << ","
        << rx.mac << ","
        << (rx.senderName.empty() && tx ? tx->senderName : rx.senderName) << ","
        << "loRaGW[0],";
    if (rx.hasRssi)
        csv << rx.rssi;
    csv << ",";
    if (rx.hasSnir)
        csv << rx.snirDb;
    csv << ",";
    if (rx.packetSizeB >= 0)
        csv << rx.packetSizeB;
    csv << ",";
    if (tx && tx->transmittedBytes >= 0)
        csv << tx->transmittedBytes;
    csv << ",";
    if (tx && !std::isnan(tx->energyJ))
        csv << tx->energyJ;
    csv << ",";
    if (seq >= 0)
        csv << seq;
    csv << ",";
    int sf = rx.sf >= 0 ? rx.sf : (tx ? tx->sf : -1);
    if (sf >= 0)
        csv << sf;
    csv << ",";
    double tpW = rx.txPowerW > 0 ? rx.txPowerW : (tx ? tx->txPowerW : 0);
    if (tpW > 0)
        csv << inet::math::mW2dBmW(tpW * 1000.0);
    csv << ",";
    int cr = rx.cr >= 0 ? rx.cr : (tx ? tx->cr : -1);
    if (cr >= 0)
        csv << cr;
    csv << ","
        << seqSeenBefore << ",";

    auto it = lastRxBySender.find(rx.mac);
    if (rx.mac.empty() || it == lastRxBySender.end())
        csv << ",";
    else
        csv << (rx.recvTime - SIMTIME_DBL(it->second)) << ",";
    if (!rx.mac.empty())
        lastRxBySender[rx.mac] = rx.recvTime;

    csv << 0 << "," << 1 << "," << labelFromActiveConfig() << "\n";
    csv.flush();
}

void PacketEventLogger::writeUnreceivedTx(const TxRecord &tx)
{
    openCsvIfNeeded();
    csv << nextPacketId++ << ","
        << SIMTIME_DBL(simTime()) << ","
        << tx.mac << ","
        << tx.senderName << ","
        << "loRaGW[0],"
        << "," << "," << ",";  // rssi snir packet_size_B (non recu)
    if (tx.transmittedBytes >= 0)
        csv << tx.transmittedBytes;
    csv << ",";
    if (!std::isnan(tx.energyJ))
        csv << tx.energyJ;
    csv << ",";
    if (tx.seq >= 0)
        csv << tx.seq;
    csv << ",";
    if (tx.sf >= 0)
        csv << tx.sf;
    csv << ",";
    if (tx.txPowerW > 0)
        csv << inet::math::mW2dBmW(tx.txPowerW * 1000.0);
    csv << ",";
    if (tx.cr >= 0)
        csv << tx.cr;
    csv << ","
        << 0 << ","   // seq_seen_before
        << ","        // interarrival
        << ","        // collision inconnue (perte ou hors portee, pas forcement collision GW)
        << 0 << ","   // received
        << labelFromActiveConfig() << "\n";
    csv.flush();
}

void PacketEventLogger::tryFlushPair(const std::string &key)
{
    auto tit = pendingTx.find(key);
    auto rit = pendingRx.find(key);
    if (tit == pendingTx.end() || rit == pendingRx.end())
        return;
    writeRxRow(rit->second, &tit->second);
    tit->second.used = true;
    rit->second.written = true;
    pendingTx.erase(tit);
    pendingRx.erase(rit);
}

void PacketEventLogger::noteTransmissionEnd(const std::string &mac, int seq, int64_t transmittedBytes,
        double energyJ, int sf, double txPowerW, int cr, const std::string &senderName)
{
    if (mac.empty() || seq < 0)
        return;
    if (!senderName.empty())
        macToName[mac] = senderName;
    TxRecord rec;
    rec.mac = mac;
    rec.senderName = senderName.empty() ? nameFromMac(mac) : senderName;
    rec.seq = seq;
    rec.transmittedBytes = transmittedBytes;
    rec.energyJ = energyJ;
    rec.sf = sf;
    rec.txPowerW = txPowerW;
    rec.cr = cr;
    std::string key = txKey(mac, seq);
    pendingTx[key] = rec;
    tryFlushPair(key);
}

void PacketEventLogger::logGatewayReception(Packet *pkt, const flora::LoRaMacFrame *frame,
        const double *rssiDbm, const double *snirLinear)
{
    RxRecord rx;
    rx.mac = frame->getTransmitterAddress().str();
    rx.senderName = nameFromMac(rx.mac);
    rx.seq = frame->getSequenceNumber();
    rx.recvTime = SIMTIME_DBL(simTime());
    rx.packetSizeB = pkt->getByteLength();
    rx.sf = frame->getLoRaSF();
    rx.txPowerW = frame->getLoRaTP();
    rx.cr = frame->getLoRaCR();
    if (rssiDbm) {
        rx.rssi = *rssiDbm;
        rx.hasRssi = true;
    }
    if (snirLinear) {
        rx.snirDb = inet::math::fraction2dB(*snirLinear);
        rx.hasSnir = true;
    }
    std::string key = txKey(rx.mac, rx.seq);
    pendingRx[key] = rx;
    tryFlushPair(key);
}

void PacketEventLogger::receiveSignal(cComponent *source, simsignal_t signalID, bool b, cObject *details)
{
    if (b)
        logCollisionIfGateway(source);
}

void PacketEventLogger::receiveSignal(cComponent *source, simsignal_t signalID, intval_t value, cObject *details)
{
    if (value)
        logCollisionIfGateway(source);
}

void PacketEventLogger::logCollisionIfGateway(cComponent *source)
{
    std::string path = source ? source->getFullPath() : "";
    if (path.find("loRaGW") == std::string::npos)
        return;
    openCsvIfNeeded();
    csv << nextPacketId++ << ","
        << SIMTIME_DBL(simTime()) << ","
        << "," << "," << "loRaGW[0],"
        << "," << "," << "," << "," << "," << "," << "," << "," << "," << "," << ","
        << 1 << ","
        << 0 << ","
        << labelFromActiveConfig() << "\n";
    csv.flush();
}

void PacketEventLogger::finish()
{
    for (auto &kv : pendingRx) {
        if (!kv.second.written) {
            const TxRecord *tx = nullptr;
            auto tit = pendingTx.find(kv.first);
            if (tit != pendingTx.end())
                tx = &tit->second;
            writeRxRow(kv.second, tx);
            kv.second.written = true;
            if (tit != pendingTx.end())
                tit->second.used = true;
        }
    }
    for (auto &kv : pendingTx) {
        if (!kv.second.used)
            writeUnreceivedTx(kv.second);
    }
    pendingTx.clear();
    pendingRx.clear();
    if (csv.is_open())
        csv.close();
}

} // namespace agrilorasec
