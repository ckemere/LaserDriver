#ifndef FRAMING_H
#define FRAMING_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/*
 * Frame assembly / disassembly for the binary wire protocol.
 *
 *   body = TYPE(u8) || payload || CRC16(TYPE||payload)  (CRC LE)
 *   wire = COBS(body) || 0x00
 *
 * Generic over message content; see protocol.h for the type/field map and
 * Pi/protocol.py for the host mirror.
 */

/* Max decoded body (TYPE + payload + 2 CRC) we will accept; COBS overhead
 * is small on top of this. */
#define FRAME_MAX_BODY     32u
#define FRAME_RX_BUF_SIZE  48u

/*
 * Assemble one wire frame into `out`.  Returns the wire length (including
 * the trailing 0x00 delimiter), or 0 if it would not fit in out_cap.
 */
size_t frame_encode(uint8_t type, const uint8_t *payload, size_t payload_len,
                    uint8_t *out, size_t out_cap);

/* Streaming decoder: feed received bytes one at a time. */
typedef struct {
    uint8_t buf[FRAME_RX_BUF_SIZE];
    size_t  len;
} FrameDecoder;

void frame_decoder_init(FrameDecoder *d);

/*
 * Push one received byte.  When `byte` is the 0x00 delimiter and the
 * accumulated block decodes to a CRC-valid frame, writes the message type
 * to *type_out and the payload (the body minus TYPE and CRC) into
 * payload_out, sets *payload_len_out, and returns true.  Otherwise returns
 * false (still accumulating, or the completed frame was malformed and
 * dropped — the decoder is reset and resyncs on the next delimiter).
 */
bool frame_decoder_push(FrameDecoder *d, uint8_t byte,
                        uint8_t *type_out,
                        uint8_t *payload_out, size_t payload_cap,
                        size_t *payload_len_out);

#endif /* FRAMING_H */
