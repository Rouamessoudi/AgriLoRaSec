#ifndef AGRILORASEC_AGRISENSORAPP_H_
#define AGRILORASEC_AGRISENSORAPP_H_

#include <omnetpp.h>
#include "inet/common/lifecycle/ILifecycle.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/lifecycle/LifecycleOperation.h"
#include "inet/common/packet/Packet.h"

#include "LoRaApp/LoRaAppPacket_m.h"
#include "LoRa/LoRaRadio.h"
#include "LoRa/LoRaTagInfo_m.h"
#include "AgriSensorPacket_m.h"

using namespace omnetpp;
using namespace inet;

namespace agrilorasec {

/**
 * Application agricole : chaque noeud envoie 3 mesures
 * (temperature, humidite sol, humidite air).
 */
class AgriSensorApp : public cSimpleModule, public ILifecycle
{
  protected:
    virtual void initialize(int stage) override;
    virtual void finish() override;
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }
    virtual void handleMessage(cMessage *msg) override;
    virtual bool handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback) override;

    void handleMessageFromLowerLayer(cMessage *msg);
    void sendSensorReading();

    int numberOfPacketsToSend = 0;
    int sentPackets = 0;
    int receivedADRCommands = 0;
    int nodeIndex = 0;
    simtime_t timeToFirstPacket;
    simtime_t timeToNextPacket;

    cMessage *sendMeasurements = nullptr;
    cMessage *channelHopTimer = nullptr;
    flora::LoRaRadio *loRaRadio = nullptr;
    bool enableChannelHop = false;
    bool channelHopDone = false;
    simtime_t channelHopTime;
    inet::units::values::Hz channelHopFrequency = inet::units::values::Hz(868.3e6);
    void applyChannelHop();

    bool evaluateADRinNode = false;
    int ADR_ACK_CNT = 0;
    int ADR_ACK_LIMIT = 64;
    int ADR_ACK_DELAY = 32;
    bool sendNextPacketWithADRACKReq = false;
    void increaseSFIfPossible();

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
    AgriSensorApp() {}
    virtual ~AgriSensorApp();
    simsignal_t LoRa_AppPacketSent;
    simsignal_t temperatureSent;
    simsignal_t soilHumiditySent;
    simsignal_t airHumiditySent;
};

} // namespace agrilorasec

#endif
