#include "framing.h"

size_t frame_encode(uint8_t type, const uint8_t *payload, size_t payload_len,
                    uint8_t *out, size_t out_cap)
{
    if (3u + payload_len > out_cap) {
        return 0u;
    }
    out[0] = PROTO_SYNC0;
    out[1] = PROTO_SYNC1;
    out[2] = type;
    for (size_t i = 0; i < payload_len; i++) {
        out[3u + i] = payload[i];
    }
    return 3u + payload_len;
}

/* Inbound (command) payload length, or -1 for an unknown/out-of-direction
 * type.  The MCU only ever decodes commands. */
static int cmd_payload_len(uint8_t type)
{
    switch (type) {
        case CMD_CONFIG:       return (int)CMD_CONFIG_LEN;
        case CMD_TRIGGER:      return 0;
        case CMD_QUERY:        return 0;
        case CMD_SET_MODE:     return (int)CMD_SET_MODE_LEN;
        case CMD_ESTIM_CONFIG: return (int)CMD_ESTIM_CONFIG_LEN;
        default:               return -1;
    }
}

void frame_decoder_init(FrameDecoder *d)
{
    d->state = FRAME_SYNC0;
    d->plen  = 0u;
    d->need  = 0u;
}

bool frame_decoder_push(FrameDecoder *d, uint8_t byte,
                        uint8_t *type_out,
                        uint8_t *payload_out, size_t payload_cap,
                        size_t *payload_len_out)
{
    switch (d->state) {
        case FRAME_SYNC0:
            if (byte == PROTO_SYNC0) {
                d->state = FRAME_SYNC1;
            }
            return false;

        case FRAME_SYNC1:
            if (byte == PROTO_SYNC1) {
                d->state = FRAME_TYPE;
            } else if (byte != PROTO_SYNC0) {
                d->state = FRAME_SYNC0;
            }
            /* byte == SYNC0: stay in SYNC1 (a run of SYNC0s). */
            return false;

        case FRAME_TYPE: {
            int n = cmd_payload_len(byte);
            if (n < 0) {
                /* Unknown type: not a real frame here.  Let this byte still
                 * be able to start the next SYNC. */
                d->state = (byte == PROTO_SYNC0) ? FRAME_SYNC1 : FRAME_SYNC0;
                return false;
            }
            d->type = byte;
            if (n == 0) {
                d->state = FRAME_SYNC0;
                *type_out = byte;
                *payload_len_out = 0u;
                return true;
            }
            d->need = (uint8_t)n;
            d->plen = 0u;
            d->state = FRAME_PAYLOAD;
            return false;
        }

        case FRAME_PAYLOAD:
            if (d->plen < PROTO_MAX_PAYLOAD) {
                d->payload[d->plen] = byte;
            }
            d->plen++;
            if (d->plen >= d->need) {
                d->state = FRAME_SYNC0;
                if (d->need <= payload_cap) {
                    *type_out = d->type;
                    for (uint8_t i = 0; i < d->need; i++) {
                        payload_out[i] = d->payload[i];
                    }
                    *payload_len_out = d->need;
                    return true;
                }
            }
            return false;

        default:
            d->state = FRAME_SYNC0;
            return false;
    }
}
