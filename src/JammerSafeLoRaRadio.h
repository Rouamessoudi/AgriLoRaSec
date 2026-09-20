#ifndef AGRILORASEC_JAMMERSAFELORARADIO_H_
#define AGRILORASEC_JAMMERSAFELORARADIO_H_

#include "LoRa/LoRaRadio.h"

namespace agrilorasec {

// FLoRa LoRaRadio jette si sendDown pendant transmissionTimer. Jammer-only: drop.
class JammerSafeLoRaRadio : public flora::LoRaRadio
{
  protected:
    virtual void handleUpperPacket(inet::Packet *packet) override;
};

} // namespace agrilorasec

#endif
