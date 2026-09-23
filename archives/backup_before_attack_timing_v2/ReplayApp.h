#ifndef AGRILORASEC_REPLAYAPP_H_
#define AGRILORASEC_REPLAYAPP_H_

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

class ReplayApp : public cSimpleModule, public cListener, public ILifecycle
{
  protected:
    virtual void initialize(int stage) override;
    virtual void finish() override;
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }
    virtual void handleMessage(cMessage *msg) override;
    virtual void receiveSignal(cComponent *source, simsignal_t signalID, cObject *obj,
            cObject *details) override;
    virtual bool handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback) override;

    void tryCaptureFromTransmission(cObject *obj);
    void tryCaptureFromTransmissionImpl(cObject *obj);
    void sendReplayPacket();
    void logPayload(const char *prefix, Packet *pkt);

    int numberOfReplays = 1;
    int replayCount = 0;
    bool captureArmed = false;
    bool hasCaptured = false;

    Packet *capturedPacket = nullptr;
    std::string capturedMac;
    int capturedSeq = -1;
    double capturedSample = NAN;
    double capturedTemperature = NAN;
    bool hasAgriPayload = false;

    cMessage *captureTimer = nullptr;
    cMessage *replayTimer = nullptr;
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
