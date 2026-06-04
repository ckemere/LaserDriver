/*
 * Host-build cross-check for the firmware codec (crc16 + cobs + framing).
 * Compiled with the native gcc (NOT the cross toolchain) and compared
 * against Pi/protocol.py by host_tools/proto_crosscheck.py.
 *
 *   cc -I.. proto_selftest.c ../crc16.c ../cobs.c ../framing.c -o /tmp/pst
 *
 * Usage:
 *   proto_selftest crc                 -> prints CRC16 of "123456789"
 *   proto_selftest encode TYPE HEX     -> prints wire frame hex
 *   proto_selftest decode HEX          -> prints "TYPE PAYLOADHEX" per frame
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "crc16.h"
#include "cobs.h"
#include "framing.h"

static int hex2bytes(const char *hex, uint8_t *out, size_t cap)
{
    size_t n = strlen(hex);
    if (n % 2u) return -1;
    size_t bytes = n / 2u;
    if (bytes > cap) return -1;
    for (size_t i = 0; i < bytes; i++) {
        unsigned v;
        if (sscanf(hex + 2u * i, "%2x", &v) != 1) return -1;
        out[i] = (uint8_t)v;
    }
    return (int)bytes;
}

static void print_hex(const uint8_t *b, size_t n)
{
    for (size_t i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "crc") == 0) {
        printf("%04x\n", crc16_ccitt((const uint8_t *)"123456789", 9));
        return 0;
    }
    if (argc == 4 && strcmp(argv[1], "encode") == 0) {
        uint8_t type = (uint8_t)strtoul(argv[2], NULL, 16);
        uint8_t payload[FRAME_MAX_BODY];
        int plen = hex2bytes(argv[3], payload, sizeof payload);
        if (plen < 0) { fprintf(stderr, "bad payload hex\n"); return 2; }
        uint8_t wire[FRAME_RX_BUF_SIZE + 4];
        size_t n = frame_encode(type, payload, (size_t)plen, wire, sizeof wire);
        if (n == 0u) { fprintf(stderr, "encode failed\n"); return 2; }
        print_hex(wire, n);
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "decode") == 0) {
        uint8_t wire[256];
        int wlen = hex2bytes(argv[2], wire, sizeof wire);
        if (wlen < 0) { fprintf(stderr, "bad wire hex\n"); return 2; }
        FrameDecoder d;
        frame_decoder_init(&d);
        for (int i = 0; i < wlen; i++) {
            uint8_t type, payload[FRAME_MAX_BODY];
            size_t plen;
            if (frame_decoder_push(&d, wire[i], &type, payload,
                                   sizeof payload, &plen)) {
                printf("%02x ", type);
                print_hex(payload, plen);
            }
        }
        return 0;
    }
    fprintf(stderr, "usage: %s crc|encode|decode ...\n", argv[0]);
    return 2;
}
