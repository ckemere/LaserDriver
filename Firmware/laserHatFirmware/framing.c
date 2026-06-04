#include "framing.h"
#include "cobs.h"
#include "crc16.h"

size_t frame_encode(uint8_t type, const uint8_t *payload, size_t payload_len,
                    uint8_t *out, size_t out_cap)
{
    uint8_t body[FRAME_MAX_BODY];
    size_t  body_len = 0u;

    if (1u + payload_len + 2u > FRAME_MAX_BODY) {
        return 0u;
    }

    body[body_len++] = type;
    for (size_t i = 0; i < payload_len; i++) {
        body[body_len++] = payload[i];
    }
    uint16_t crc = crc16_ccitt(body, body_len);
    body[body_len++] = (uint8_t)(crc & 0xFFu);
    body[body_len++] = (uint8_t)(crc >> 8);

    /* COBS-encode the body into out, then append the 0x00 delimiter. */
    size_t enc = cobs_encode(body, body_len, out, out_cap);
    if (enc == 0u || enc + 1u > out_cap) {
        return 0u;
    }
    out[enc] = 0x00u;
    return enc + 1u;
}

void frame_decoder_init(FrameDecoder *d)
{
    d->len = 0u;
}

bool frame_decoder_push(FrameDecoder *d, uint8_t byte,
                        uint8_t *type_out,
                        uint8_t *payload_out, size_t payload_cap,
                        size_t *payload_len_out)
{
    if (byte != 0x00u) {
        if (d->len < FRAME_RX_BUF_SIZE) {
            d->buf[d->len++] = byte;
        } else {
            d->len = 0u;        /* runaway frame; drop and resync */
        }
        return false;
    }

    /* Delimiter: try to decode whatever we've accumulated. */
    size_t block_len = d->len;
    d->len = 0u;
    if (block_len == 0u) {
        return false;           /* empty (e.g. back-to-back delimiters) */
    }

    uint8_t body[FRAME_MAX_BODY];
    size_t  body_len = cobs_decode(d->buf, block_len, body, sizeof body);
    if (body_len < 3u) {
        return false;           /* malformed or runt */
    }

    size_t   data_len = body_len - 2u;
    uint16_t want = (uint16_t)body[data_len] | ((uint16_t)body[data_len + 1u] << 8);
    if (crc16_ccitt(body, data_len) != want) {
        return false;           /* CRC mismatch; drop */
    }

    /* data = TYPE || payload */
    *type_out = body[0];
    size_t payload_len = data_len - 1u;
    if (payload_len > payload_cap) {
        return false;
    }
    for (size_t i = 0; i < payload_len; i++) {
        payload_out[i] = body[1u + i];
    }
    *payload_len_out = payload_len;
    return true;
}
