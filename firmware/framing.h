#ifndef FRAMING_H
#define FRAMING_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "protocol.h"

/*
 * Magic-word framing for the binary wire protocol (see protocol.h).
 *
 *   wire = SYNC(DE AD) | TYPE | payload (length implied by TYPE)
 *
 * No length field, no stuffing, no CRC.  The decoder scans for SYNC, reads
 * TYPE, then the fixed number of payload bytes for that (inbound, command)
 * type.  The host guarantees a CMD_CONFIG payload never contains the SYNC
 * bytes, so resync on the next SYNC is exact.
 */

/* Assemble one wire frame into `out`.  Returns the wire length, or 0 if it
 * would not fit in out_cap. */
size_t frame_encode(uint8_t type, const uint8_t *payload, size_t payload_len,
                    uint8_t *out, size_t out_cap);

typedef enum {
    FRAME_SYNC0,    /* hunting for SYNC byte 0 */
    FRAME_SYNC1,    /* got SYNC0, expecting SYNC1 */
    FRAME_TYPE,     /* SYNC seen, next byte is TYPE */
    FRAME_PAYLOAD,  /* reading payload */
} FrameState;

typedef struct {
    FrameState state;
    uint8_t    type;
    uint8_t    need;
    uint8_t    plen;
    uint8_t    payload[PROTO_MAX_PAYLOAD];
} FrameDecoder;

void frame_decoder_init(FrameDecoder *d);

/*
 * Push one received byte.  Returns true and fills *type_out / payload_out /
 * *payload_len_out when a complete command frame is decoded; false while
 * still accumulating or hunting for the next SYNC.
 */
bool frame_decoder_push(FrameDecoder *d, uint8_t byte,
                        uint8_t *type_out,
                        uint8_t *payload_out, size_t payload_cap,
                        size_t *payload_len_out);

#endif /* FRAMING_H */
