#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

/*
 * LaserHat binary wire protocol — firmware (MCU) side.
 *
 * This header is the firmware mirror of Pi/protocol.py.  The two MUST
 * stay in sync: if you change a message type or field layout here, change
 * it there too.
 *
 * Frame layout (both directions):
 *
 *   payload = TYPE(u8) || fields (little-endian, fixed width)
 *   body    = payload  || CRC16_CCITT(payload)   (CRC as 2 bytes, LE)
 *   wire    = COBS(body) || 0x00                  (0x00 is the delimiter)
 *
 * COBS (see cobs.h) guarantees the encoded bytes never contain 0x00, so
 * the delimiter unambiguously ends a frame and the decoder resyncs on it.
 * A frame whose CRC fails (or fails to COBS-decode) is dropped; the next
 * 0x00 starts a fresh frame.  See framing.h for encode/decode helpers.
 */

/* Host -> MCU (commands).  High bit clear. */
#define CMD_SET_INTENSITY   0x01u   /* u16 */
#define CMD_SET_RAMP        0x02u   /* u32 */
#define CMD_SET_HOLD        0x03u   /* u32 */
#define CMD_TRIGGER         0x04u   /* (no fields) */
#define CMD_ARM             0x05u   /* (no fields) */
#define CMD_QUERY           0x06u   /* (no fields) */

/* MCU -> Host (responses + events).  High bit set. */
#define RSP_ACK             0x81u   /* u8 cmd_type, u8 status */
#define RSP_STATUS          0x82u   /* u16 i, u32 r, u32 h, u8 btn, u8 armed, u8 phase, u32 tick */
#define EVT_PULSE_START     0x83u   /* u32 tick */
#define EVT_PULSE_END       0x84u   /* u32 tick */
#define EVT_BUTTON          0x85u   /* u8 mask, u8 edges */

/* RSP_ACK status codes (second byte). */
#define ACK_OK              0x00u
#define ACK_RANGE           0x01u
#define ACK_BUSY            0x02u
#define ACK_UNKNOWN         0x03u

/* Phase byte values in RSP_STATUS (ASCII 'W' / 'T'). */
#define PHASE_WAITING       0x57u   /* 'W' */
#define PHASE_TRIGGERED     0x54u   /* 'T' */

/*
 * RSP_STATUS field portion is 17 bytes, packed little-endian with NO
 * padding (matches Python struct "<HIIBBBI"):
 *   off 0  : u16 intensity
 *   off 2  : u32 ramp_ticks
 *   off 6  : u32 hold_ticks
 *   off 10 : u8  button_mask
 *   off 11 : u8  armed (0/1)
 *   off 12 : u8  phase ('W'/'T')
 *   off 13 : u32 tick
 * The firmware writes these bytes by hand (see emit_status) rather than
 * memcpy'ing a struct, to avoid any compiler padding.
 */
#define PROTO_STATUS_FIELD_LEN   17u

/* Largest payload (TYPE + fields) we assemble or accept. */
#define PROTO_MAX_PAYLOAD        24u

#endif /* PROTOCOL_H */
