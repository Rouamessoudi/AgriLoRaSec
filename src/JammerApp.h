#ifndef AGRILORASEC_JAMMERAPP_H_
#define AGRILORASEC_JAMMERAPP_H_

#include <omnetpp.h>
#include "inet/common/lifecycle/ILifecycle.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/lifecycle/LifecycleOperation.h"
#include "inet/common/packet/Packet.h"

#include "LoRaApp/LoRaAppPacket_m.h"
#include "LoRa/LoRaRadio.h"
#include "LoRa/LoRaTagInfo_m.h"

using namespace omnetpp;
using namespace inet;

namespace agrilorasec {

class JammerApp : public cSimpleModule, public cListener, public ILifecycle
{
  protected:
    virtual void initialize(int stage) override;
    virtual void finish() override;
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }
    virtual void handleMessage(cMessage *msg) override;
    virtual void receiveSignal(cComponent *source, simsignal_t signalID, intval_t value,
            cObject *details) override;
    virtual bool handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback) override;

    void sendJammingPacket();
    void scheduleNextAfterPhyTx();
    bool inAttackWindow() const;

    int numberOfPacketsToSend = 0;
    int sentPackets = 0;
    simtime_t timeToFirstPacket;
    simtime_t attackStart = 0;
    simtime_t attackEnd = 0;
    bool awaitingPhyTxEnd = false;
    bool sawPhyTransmitting = false;
    simtime_t lastPhyTxStart = 0;
    simtime_t lastPhyAirtime = 0;
    cMessage *sendJamming = nullptr;
    cMessage *attackStartTimer = nullptr;
    cMessage *attackEndTimer = nullptr;
    flora::LoRaRadio *loRaRadio = nullptr;

    // Jammer: TX puis petit gap. Pas de fenetres RX Class A (MAC jammer force IDLE).
    static constexpr double floraPostTxMacWindowsS = 0.0;

    void setSF(int SF);
    int getSF();
    void setTP(int TP);
    double getTP();
    void setCR(int CR);
    int getCR();
    void setCF(units::values::Hz CF);
    units::values::Hz getCF();
    void setBW(units::values::Hz BW);
    units::values::Hz getBW();

  public:
    JammerApp() {}
    virtual ~JammerApp();
    simsignal_t jammingPacketSent;
};

} // namespace agrilorasec

#endif
