#include "cobs.h"

/*
 * Encode `in` so the result contains no 0x00.  Returns encoded length, or
 * 0 if it would not fit in out_cap.  The caller appends the 0x00 delimiter.
 */
size_t cobs_encode(const uint8_t *in, size_t in_len,
                   uint8_t *out, size_t out_cap)
{
    if (out_cap == 0u) {
        return 0u;
    }

    size_t  read   = 0u;
    size_t  write  = 0u;
    size_t  code_i = write++;   /* reserve slot for the first code byte */
    uint8_t code   = 1u;

    if (write > out_cap) {
        return 0u;
    }

    while (read < in_len) {
        uint8_t byte = in[read++];
        if (byte != 0u) {
            if (write >= out_cap) {
                return 0u;
            }
            out[write++] = byte;
            code++;
            if (code == 0xFFu) {
                out[code_i] = code;
                code_i = write++;
                code = 1u;
                if (write > out_cap) {
                    return 0u;
                }
            }
        } else {
            out[code_i] = code;
            code_i = write++;
            code = 1u;
            if (write > out_cap) {
                return 0u;
            }
        }
    }
    out[code_i] = code;
    return write;
}

/*
 * Decode a COBS block (without the trailing 0x00 delimiter).  Returns the
 * decoded length, or 0 on malformed input (embedded 0x00, a code that
 * overruns the block, or output that won't fit).
 */
size_t cobs_decode(const uint8_t *in, size_t in_len,
                   uint8_t *out, size_t out_cap)
{
    size_t read  = 0u;
    size_t write = 0u;

    while (read < in_len) {
        uint8_t code = in[read];
        if (code == 0u) {
            return 0u;                  /* 0x00 never appears in a block */
        }
        read++;
        /* Copy (code - 1) literal bytes. */
        for (uint8_t i = 1u; i < code; i++) {
            if (read >= in_len) {
                return 0u;              /* code overruns the input */
            }
            if (write >= out_cap) {
                return 0u;
            }
            out[write++] = in[read++];
        }
        /* A code < 0xFF implies an elided 0x00, unless we're at the end. */
        if (code != 0xFFu && read < in_len) {
            if (write >= out_cap) {
                return 0u;
            }
            out[write++] = 0u;
        }
    }
    return write;
}
