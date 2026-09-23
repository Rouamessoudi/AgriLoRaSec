#include "AgriSensorApp.h"
#include "inet/mobility/static/StationaryMobility.h"
#include "LoRa/LoRaMacFrame_m.h"

namespace agrilorasec {

Define_Module(AgriSensorApp);

AgriSensorApp::~AgriSensorApp()
{
    cancelAndDelete(sendMeasurements);
}

void AgriSensorApp::initialize(int stage)
{
    cSimpleModule::initialize(stage);
    if (stage == INITSTAGE_APPLICATION_LAYER) {
        bool isOperational;
        NodeStatus *nodeStatus = dynamic_cast<NodeStatus *>(findContainingNode(this)->getSubmodule("status"));
        isOperational = (!nodeStatus) || nodeStatus->getState() == NodeStatus::UP;
        if (!isOperational)
            throw cRuntimeError("This module doesn't support starting in node DOWN state");

        // Index du noeud depuis le nom parent (loRaNode0 .. loRaNode9)
        nodeIndex = 0;
        cModule *host = getContainingNode(this);
        std::string hostName = host->getName();
        if (hostName.rfind("loRaNode", 0) == 0 && hostName.size() > 8)
            nodeIndex = atoi(hostName.substr(8).c_str());

        do {
            timeToFirstPacket = par("timeToFirstPacket");
        } while (timeToFirstPacket <= 5);

        sendMeasurements = new cMessage("sendMeasurements");
        scheduleAt(simTime() + timeToFirstPacket, sendMeasurements);

        sentPackets = 0;
        receivedADRCommands = 0;
        numberOfPacketsToSend = par("numberOfPacketsToSend");

        LoRa_AppPacketSent = registerSignal("LoRa_AppPacketSent");
        temperatureSent = registerSignal("temperatureSent");
        soilHumiditySent = registerSignal("soilHumiditySent");
        airHumiditySent = registerSignal("airHumiditySent");

        loRaRadio = check_and_cast<flora::LoRaRadio *>(getParentModule()->getSubmodule("LoRaNic")->getSubmodule("radio"));
        loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
        loRaRadio->loRaCF = units::values::Hz(par("initialLoRaCF").doubleValue());
        loRaRadio->loRaSF = par("initialLoRaSF");
        loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
        loRaRadio->loRaCR = par("initialLoRaCR");
        loRaRadio->loRaUseHeader = par("initialUseHeader");
        evaluateADRinNode = par("evaluateADRinNode");

        EV_INFO << "AgriSensorApp init on " << hostName
                << " (nodeIndex=" << nodeIndex
                << ") with 3 sensors: temperature, soilHumidity, airHumidity\n";
    }
}

void AgriSensorApp::finish()
{
    recordScalar("sentPackets", sentPackets);
    recordScalar("receivedADRCommands", receivedADRCommands);
    recordScalar("nodeIndex", nodeIndex);
}

void AgriSensorApp::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        if (msg == sendMeasurements) {
            sendSensorReading();
            if (simTime() >= getSimulation()->getWarmupPeriod())
                sentPackets++;
            delete msg;
            sendMeasurements = nullptr;

            if (numberOfPacketsToSend == 0 || sentPackets < numberOfPacketsToSend) {
                double airTime = 171.2128;
                int loRaSF = getSF();
                if (loRaSF == 7) airTime = 7.808;
                else if (loRaSF == 8) airTime = 13.9776;
                else if (loRaSF == 9) airTime = 24.6784;
                else if (loRaSF == 10) airTime = 49.3568;
                else if (loRaSF == 11) airTime = 85.6064;
                else airTime = 171.2128;

                do {
                    timeToNextPacket = par("timeToNextPacket");
                } while (timeToNextPacket <= airTime);

                sendMeasurements = new cMessage("sendMeasurements");
                scheduleAt(simTime() + timeToNextPacket, sendMeasurements);
            }
        }
    }
    else {
        handleMessageFromLowerLayer(msg);
        delete msg;
    }
}

void AgriSensorApp::handleMessageFromLowerLayer(cMessage *msg)
{
    auto pkt = check_and_cast<Packet *>(msg);
    Ptr<const flora::LoRaAppPacket> packet = nullptr;
    try {
        auto front = pkt->peekAtFront();
        packet = dynamicPtrCast<const flora::LoRaAppPacket>(front);
        if (packet == nullptr && dynamicPtrCast<const flora::LoRaMacFrame>(front) != nullptr) {
            pkt->popAtFront<flora::LoRaMacFrame>();
            packet = dynamicPtrCast<const flora::LoRaAppPacket>(pkt->peekAtFront());
        }
    }
    catch (cRuntimeError&) {
        return;
    }
    if (packet == nullptr)
        return;
    if (simTime() >= getSimulation()->getWarmupPeriod())
        receivedADRCommands++;
    if (evaluateADRinNode) {
        ADR_ACK_CNT = 0;
        if (packet->getMsgType() == flora::TXCONFIG) {
            if (packet->getOptions().getLoRaTP() != -1)
                setTP(packet->getOptions().getLoRaTP());
            if (packet->getOptions().getLoRaSF() != -1)
                setSF(packet->getOptions().getLoRaSF());
        }
    }
}

bool AgriSensorApp::handleOperationStage(LifecycleOperation *operation, IDoneCallback *doneCallback)
{
    Enter_Method_Silent();
    throw cRuntimeError("Unsupported lifecycle operation '%s'", operation->getClassName());
    return true;
}

void AgriSensorApp::sendSensorReading()
{
    // --- 3 capteurs agricoles ---
    double temperature = uniform(par("minTemperature").doubleValue(), par("maxTemperature").doubleValue());
    double soilHumidity = uniform(par("minSoilHumidity").doubleValue(), par("maxSoilHumidity").doubleValue());
    double airHumidity = uniform(par("minAirHumidity").doubleValue(), par("maxAirHumidity").doubleValue());

    EV_INFO << "Node" << nodeIndex
            << " SEND sensors:"
            << " temperature=" << temperature << " C,"
            << " soilHumidity=" << soilHumidity << " %,"
            << " airHumidity=" << airHumidity << " %\n";

    emit(temperatureSent, temperature);
    emit(soilHumiditySent, soilHumidity);
    emit(airHumiditySent, airHumidity);

    char pktName[96];
    sprintf(pktName, "AgriN%d_T%.1f_Soil%.1f_Air%.1f", nodeIndex, temperature, soilHumidity, airHumidity);
    auto pktRequest = new Packet(pktName);
    pktRequest->setKind(flora::DATA);

    // Chunk compatible FLoRa (NetworkServer)
    auto loraPayload = makeShared<flora::LoRaAppPacket>();
    loraPayload->setChunkLength(B(par("dataSize").intValue()));
    loraPayload->setMsgType(flora::DATA);
    loraPayload->setSampleMeasurement((int)(temperature * 10)); // compat FLoRa
    if (evaluateADRinNode && sendNextPacketWithADRACKReq) {
        auto opt = loraPayload->getOptions();
        opt.setADRACKReq(true);
        loraPayload->setOptions(opt);
        sendNextPacketWithADRACKReq = false;
    }

    // Chunk PFE : les 3 capteurs
    auto agriPayload = makeShared<AgriSensorPacket>();
    agriPayload->setChunkLength(B(16));
    agriPayload->setTemperature(temperature);
    agriPayload->setSoilHumidity(soilHumidity);
    agriPayload->setAirHumidity(airHumidity);
    agriPayload->setNodeIndex(nodeIndex);

    auto loraTag = pktRequest->addTagIfAbsent<flora::LoRaTag>();
    loraTag->setBandwidth(getBW());
    loraTag->setCenterFrequency(getCF());
    loraTag->setSpreadFactor(getSF());
    loraTag->setCodeRendundance(getCR());
    loraTag->setPower(mW(math::dBmW2mW(getTP())));

    pktRequest->insertAtBack(loraPayload);
    pktRequest->insertAtBack(agriPayload);
    send(pktRequest, "socketOut");

    if (evaluateADRinNode) {
        ADR_ACK_CNT++;
        if (ADR_ACK_CNT == ADR_ACK_LIMIT)
            sendNextPacketWithADRACKReq = true;
        if (ADR_ACK_CNT >= ADR_ACK_LIMIT + ADR_ACK_DELAY) {
            ADR_ACK_CNT = 0;
            increaseSFIfPossible();
        }
    }
    emit(LoRa_AppPacketSent, (long)getSF());
}

void AgriSensorApp::increaseSFIfPossible()
{
    if (getSF() < 12)
        setSF(getSF() + 1);
}

void AgriSensorApp::setSF(int SF) { loRaRadio->loRaSF = SF; }
int AgriSensorApp::getSF() { return loRaRadio->loRaSF; }
void AgriSensorApp::setTP(int TP) { loRaRadio->loRaTP = TP; }
double AgriSensorApp::getTP() { return loRaRadio->loRaTP; }
void AgriSensorApp::setCF(units::values::Hz CF) { loRaRadio->loRaCF = CF; }
units::values::Hz AgriSensorApp::getCF() { return loRaRadio->loRaCF; }
void AgriSensorApp::setBW(units::values::Hz BW) { loRaRadio->loRaBW = BW; }
units::values::Hz AgriSensorApp::getBW() { return loRaRadio->loRaBW; }
void AgriSensorApp::setCR(int CR) { loRaRadio->loRaCR = CR; }
int AgriSensorApp::getCR() { return loRaRadio->loRaCR; }

} // namespace agrilorasec
