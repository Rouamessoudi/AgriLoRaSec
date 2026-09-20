#ifndef AGRILORASEC_REPLAYAPP_H_
#define AGRILORASEC_REPLAYAPP_H_

#include <omnetpp.h>
#include <deque>
#include <set>
#include <string>
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

struct PendingReplay {
    Packet *pkt = nullptr;
    std::string mac;
    int seq = -1;
    simtime_t due = 0;
    simtime_t captureTime = 0;
    double delayS = 0;
};

class ReplayApp : public cSimpleModule, public cListener, public ILifecycle
{
  protected:
    virtual void initialize(int stage) override;
    virtual void finish() override;
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }
    virtual void handleMessage(cMessage *msg) override;
    virtual void receiveSignal(cComponent *source, simsignal_t signalID, cObject *obj,
            cObject *details) override;
    virtual void receiveSignal(cComponent *source, simsignal_t signalID, intval_t value,
            cObject *details) override;
    virtual bool handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback) override;

    void tryCaptureFromTransmission(cObject *obj);
    void tryCaptureFromTransmissionImpl(cObject *obj);
    void sendReplayPacket();
    void logPayload(const char *prefix, Packet *pkt);
    void armCapture();
    void disarmCapture();
    void clearPending();
    void scheduleReplayTimer();
    void markTxSubmitted();
    void scheduleClassAResume();
    bool radioIsTransmitting() const;
    bool inAttackWindow() const;
    static bool isLegitimateSensorName(const std::string &n);
    // FLoRa LoRaMac: waitDelay1+listening1+waitDelay2+listening2 = 4 s
    static constexpr double kClassAWindowsS = 4.0;
    static constexpr double kMacIdleMarginS = 0.05;

    int numberOfReplays = 0;
    int maxPendingReplays = 4;
    int replayCount = 0;
    int captureCount = 0;
    int dropQueue = 0;
    int dropDup = 0;
    int dropRaw = 0;
    bool captureArmed = false;
    bool mediumSubscribed = false;
    bool txBusy = false;
    bool awaitingPhyTxEnd = false;
    bool sawPhyTransmitting = false;
    simtime_t lastPhyTxStart = 0;
    simtime_t lastPhyAirtime = 0;

    simtime_t attackStart = 0;
    simtime_t attackEnd = 0;

    std::set<std::string> seenKeys;
    std::deque<PendingReplay> pending;

    cMessage *attackStartTimer = nullptr;
    cMessage *attackEndTimer = nullptr;
    cMessage *replayTimer = nullptr;
    cMessage *txFreeTimer = nullptr;
    cModule *medium = nullptr;
    flora::LoRaRadio *loRaRadio = nullptr;

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
    ReplayApp() {}
    virtual ~ReplayApp();
    simsignal_t replayPacketSent;
};

} // namespace agrilorasec

#endif
