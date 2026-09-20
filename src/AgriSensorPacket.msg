// Message agricole : 3 capteurs par noeud
import inet.common.INETDefs;
import inet.common.packet.chunk.Chunk;

namespace agrilorasec;

class AgriSensorPacket extends inet::FieldsChunk
{
    double temperature;   // temperature (C)
    double soilHumidity;  // humidite du sol (%)
    double airHumidity;   // humidite de l'air (%)
    int nodeIndex;        // numero du noeud 0..9
}
