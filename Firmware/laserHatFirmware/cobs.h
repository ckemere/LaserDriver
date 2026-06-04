#ifndef COBS_H
#define COBS_H

#include <stdint.h>
#include <stddef.h>

/*
 * Consistent Overhead Byte Stuffing.  Matches Pi/protocol.py.
 *
 * The encoded output never contains a 0x00 byte, so a 0x00 delimiter can
 * be appended to mark the end of a frame and a receiver can always resync
 * on it.  Both functions write into a caller-supplied buffer and return
 * the number of bytes written, or 0 on a buffer-too-small / malformed
 * error.
 */

/* Worst-case encoded length for an input of `n` bytes (one overhead byte
 * per 254 data bytes, plus the leading code byte). */
#define COBS_ENCODE_MAX(n)   ((n) + ((n) / 254u) + 1u)

size_t cobs_encode(const uint8_t *in, size_t in_len,
                   uint8_t *out, size_t out_cap);

size_t cobs_decode(const uint8_t *in, size_t in_len,
                   uint8_t *out, size_t out_cap);

#endif /* COBS_H */
