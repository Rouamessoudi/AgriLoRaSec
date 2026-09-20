package agrilorasec;

import flora.LoRa.LoRaMac;

// MAC du replayer : rejoue une trame LoRaMacFrame déjà formée (MAC+seq d'origine).
module PreserveHeaderLoRaMac extends LoRaMac
{
    parameters:
        @class(agrilorasec::PreserveHeaderLoRaMac);
}
