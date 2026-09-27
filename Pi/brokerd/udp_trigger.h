#ifndef UDP_TRIGGER_H
#define UDP_TRIGGER_H

#include <stdint.h>

/*
 * LaserHAT network trigger protocol (UDP).  Mirror of Pi/udp_trigger.py;
 * keep them in sync.
 *
 * One datagram = one request.  All fields little-endian, no padding.
 *
 * Request (20 bytes), sender -> broker:
 *     magic u32 "LHTR" | version u8 | type u8 | flags u16 (0) |
 *     seq u32 | client_ts u64 (opaque; echoed back)
 *
 * Reply (36 bytes), broker -> sender, sent AFTER the GPIO edge:
 *     magic u32 "LHTR" | version u8 | type u8 (LHT_ACK) | status u8 |
 *     flags u8 | seq u32 | client_ts u64 |
 *     rx_ns u64 (Pi CLOCK_REALTIME the datagram arrived: kernel timestamp) |
 *     edge_ns u64 (Pi CLOCK_REALTIME the GPIO line went high)
 *
 * edge_ns - rx_ns is the in-Pi latency (network stack + wakeup + GPIO).
 *
 * Delivery model: at-most-once.  A trigger that arrives late is worse than
 * one that never arrives, so nothing is retransmitted automatically.  The
 * sender decides whether to retry a missing ACK; a retry carries the SAME
 * seq, and the broker answers LHT_DUPLICATE (with the original edge_ns)
 * instead of firing twice.
 */

#define LHT_MAGIC       0x5254484Cu     /* bytes "LHTR" */
#define LHT_VERSION     1u
#define LHT_DEFAULT_PORT 17017u

/* Request types. */
#define LHT_TRIGGER     0x01u   /* fire a pulse */
#define LHT_PING        0x02u   /* answer only; never touches the GPIO */

/* Reply type. */
#define LHT_ACK         0x81u

/* Reply status. */
#define LHT_FIRED           0u  /* GPIO edge generated */
#define LHT_DUPLICATE       1u  /* seq already fired; edge_ns is the original */
#define LHT_PONG            2u  /* reply to LHT_PING */
#define LHT_BAD_VERSION     3u
#define LHT_BAD_TYPE        4u
#define LHT_NO_GPIO         5u  /* broker has no GPIO backend; nothing fired */

/* Reply flags (informational; the edge was generated regardless). */
#define LHT_F_MCU_BUSY      0x01u   /* MCU was mid-pulse: it ignores the edge */
#define LHT_F_MCU_DOWN      0x02u   /* broker has no recent MCU status */
#define LHT_F_GPIO_SIM      0x04u   /* simulated GPIO (off-hardware testing) */
#define LHT_F_RX_TS_USER    0x08u   /* rx_ns is a userspace, not kernel, stamp */

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint8_t  version;
    uint8_t  type;
    uint16_t flags;
    uint32_t seq;
    uint64_t client_ts;
} LhtRequest;

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint8_t  version;
    uint8_t  type;
    uint8_t  status;
    uint8_t  flags;
    uint32_t seq;
    uint64_t client_ts;
    uint64_t rx_ns;
    uint64_t edge_ns;
} LhtReply;

_Static_assert(sizeof(LhtRequest) == 20, "LhtRequest layout drift");
_Static_assert(sizeof(LhtReply)   == 36, "LhtReply layout drift");

#endif /* UDP_TRIGGER_H */
