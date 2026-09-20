package agrilorasec;

// Logger global : une ligne CSV par evenement radio observe (reception GW ou collision).
simple PacketEventLogger
{
    parameters:
        @class(agrilorasec::PacketEventLogger);
        @display("p=303,80;i=block/table");
        // Fichier CSV (relatif au repertoire de simulation)
        string outputFile = default("results/packet_events.csv");
}
