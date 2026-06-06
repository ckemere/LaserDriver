#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

/*
 * LaserHat binary wire protocol — firmware (MCU) side.
 * Mirror of Pi/protocol.py; keep them in sync.
 *
 * Frame: SYNC(2: DE AD) | TYPE(1) | payload (length implied by TYPE)
 *
 * Magic-word framing — scan for SYNC, read TYPE, read the fixed payload
 * length TYPE implies.  No length field, no byte-stuffing, no CRC:
 *
 *   - Every command is answered with RSP_STATUS ("status-as-ack"), so the
 *     host confirms end-to-end that the MCU holds the values it sent.
 *   - The MCU's only inbound payload is CMD_CONFIG (bounded i/r/h), and the
 *     host guarantees a CONFIG payload never contains the SYNC bytes, so the
 *     MCU resyncs exactly on the next SYNC without a CRC.
 */

/* SYNC bytes (both >= 0x99 so they can only collide with the low 16 bits of
 * ramp/hold — which the host nudges away). */
#define PROTO_SYNC0   0xDEu
#define PROTO_SYNC1   0xADu

/* Host -> MCU (commands). */
#define CMD_CONFIG    0x01u   /* i u16, r u32, h u32 */
#define CMD_TRIGGER   0x02u   /* (no payload) */
#define CMD_QUERY     0x03u   /* (no payload) */

/* MCU -> Host (responses + events). */
#define RSP_STATUS        0x81u   /* i u16, r u32, h u32, btn u8, phase u8, tick u32 */
#define EVT_PULSE_START   0x82u   /* tick u32 */
#define EVT_PULSE_END     0x83u   /* tick u32 */
#define EVT_BUTTON        0x84u   /* mask u8, edges u8 */

/* Phase byte values in RSP_STATUS (ASCII 'W' / 'T'). */
#define PHASE_WAITING     0x57u
#define PHASE_TRIGGERED   0x54u

/* Inbound (command) payload lengths. */
#define CMD_CONFIG_LEN    10u   /* i(2) + r(4) + h(4) */

/*
 * CMD_CONFIG payload, little-endian, no padding (Python struct "<HII"):
 *   off 0 : u16 intensity
 *   off 2 : u32 ramp_ticks
 *   off 6 : u32 hold_ticks
 *
 * RSP_STATUS payload, little-endian (Python struct "<HIIBBI"), 16 bytes:
 *   off 0  : u16 intensity
 *   off 2  : u32 ramp_ticks
 *   off 6  : u32 hold_ticks
 *   off 10 : u8  button_mask
 *   off 11 : u8  phase ('W'/'T')
 *   off 12 : u32 tick
 */
#define PROTO_STATUS_LEN    16u

/* Largest payload (inbound or outbound) we assemble or accept. */
#define PROTO_MAX_PAYLOAD   16u

#endif /* PROTOCOL_H */
