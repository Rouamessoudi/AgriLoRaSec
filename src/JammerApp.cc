#include "JammerApp.h"

namespace agrilorasec {

Define_Module(JammerApp);

JammerApp::~JammerApp()
{
    cancelAndDelete(sendJamming);
}

void JammerApp::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == INITSTAGE_APPLICATION_LAYER) {
        bool isOperational;
        NodeStatus *nodeStatus = dynamic_cast<NodeStatus *>(findContainingNode(this)->getSubmodule("status"));
        isOperational = (!nodeStatus) || nodeStatus->getState() == NodeStatus::UP;
        if (!isOperational)
            throw cRuntimeError("This module doesn't support starting in node DOWN state");

        timeToFirstPacket = par("timeToFirstPacket");
        if (timeToFirstPacket < 0)
            timeToFirstPacket = 0;

        sendJamming = new cMessage("sendJamming");
        scheduleAt(simTime() + timeToFirstPacket, sendJamming);

        sentPackets = 0;
        numberOfPacketsToSend = par("numberOfPacketsToSend");
        jammingPacketSent = registerSignal("jammingPacketSent");

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");

        EV_INFO << "JammerApp started: will jam LoRa channel (SF="
                << getSF() << ", frequent transmissions)\n";
    }
}

void JammerApp::finish()
{
    recordScalar("jammingPacketsSent", sentPackets);
}

void JammerApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == sendJamming) {
            sendJammingPacket();
            if (simTime() >= getSimulation()->getWarmupPeriod())
                sentPackets++;
            delete msg;
            sendJamming = nullptr;

            if (numberOfPacketsToSend == 0 || sentPackets < numberOfPacketsToSend) {
                // Envoyer des que possible apres le temps air (jamming continu)
                double gap = par("timeToNextPacket").doubleValue();
                if (gap < 0)
                    gap = 0;
                double wait = airTimeForSF(getSF()) + gap;
                sendJamming = new cMessage("sendJamming");
                scheduleAt(simTime() + wait, sendJamming);
            }
        }
    }
    else {
        // Ignorer les reponses / paquets recus : le jammer ne traite pas les mesures
        delete msg;
    }
}

bool JammerApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
}

double JammerApp::airTimeForSF(int sf) const
{
    if (sf == 7) return 7.808;
    if (sf == 8) return 13.9776;
    if (sf == 9) return 24.6784;
    if (sf == 10) return 49.3568;
    if (sf == 11) return 85.6064;
    return 171.2128; // SF12
}

void JammerApp::sendJammingPacket()
{
    EV_INFO << "JAMMER SEND jamming packet #" << (sentPackets + 1) << "\n";

    auto pktRequest = new Packet("JAMMING_PACKET");
    pktRequest->setKind(flora::DATA);

    auto payload = makeShared<flora::LoRaAppPacket>();
    payload->setChunkLength(B(par("dataSize").intValue()));
    payload->setMsgType(flora::DATA);
    payload->setSampleMeasurement(-1); // pas une mesure agricole

    auto loraTag = pktRequest->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(getBW());
    loraTag->setCenterFrequency(getCF());
    loraTag->setSpreadFactor(getSF());
    loraTag->setCodeRendundance(getCR());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    pktRequest->insertAtBack(payload);
    send(pktRequest, "socketOut");
    emit(jammingPacketSent, 1L);
}

void JammerApp::setSF(int SF) { loRaRadio->loRaSF = SF; }
int JammerApp::getSF() { return loRaRadio->loRaSF; }
void JammerApp::setTP(int TP) { loRaRadio->loRaTP = TP; }
double JammerApp::getTP() { return loRaRadio->loRaTP; }
void JammerApp::setCF(units::values::Hz CF) { loRaRadio->loRaCF = CF; }
units::values::Hz JammerApp::getCF() { return loRaRadio->loRaCF; }
void JammerApp::setBW(units::values::Hz BW) { loRaRadio->loRaBW = BW; }
units::values::Hz JammerApp::getBW() { return loRaRadio->loRaBW; }
void JammerApp::setCR(int CR) { loRaRadio->loRaCR = CR; }
int JammerApp::getCR() { return loRaRadio->loRaCR; }

} // namespace agrilorasec
