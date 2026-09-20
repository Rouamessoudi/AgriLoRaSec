package agrilorasec;

import flora.LoRaEnergyModules.LoRaEnergyConsumer;

// Meme modele energetique FLoRa + journal du delta d'energie par transmission.
simple LoggingLoRaEnergyConsumer extends LoRaEnergyConsumer
{
    parameters:
        @class(agrilorasec::LoggingLoRaEnergyConsumer);
}
