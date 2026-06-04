#ifndef CRC16_H
#define CRC16_H

#include <stdint.h>
#include <stddef.h>

/*
 * CRC16-CCITT: polynomial 0x1021, initial value 0xFFFF, no final XOR,
 * bytes processed MSB-first.  Matches Pi/protocol.py crc16_ccitt().
 * Bitwise (table-free) — a few hundred cycles per frame, negligible
 * against the 115200-baud link.
 */
uint16_t crc16_ccitt(const uint8_t *data, size_t len);

#endif /* CRC16_H */
