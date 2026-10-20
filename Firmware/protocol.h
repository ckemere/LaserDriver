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
 *     host confirms end-to-end that the MCU holds the values it sent
 *     (CMD_GET_VERSION -> RSP_VERSION is the one exception).
 *   - The MCU's inbound payloads are bounded (CMD_CONFIG i/r/h, the two
 *     DAC codes <= 0x0FFF, mode / estim ticks) and the host guarantees a
 *     CONFIG payload never contains the SYNC bytes, so the MCU resyncs
 *     exactly on the next SYNC without a CRC.
 */

/* SYNC bytes (both >= 0x99 so they can only collide with the low 16 bits of
 * ramp/hold — which the host nudges away). */
#define PROTO_SYNC0   0xDEu
#define PROTO_SYNC1   0xADu

/* Host -> MCU (commands). */
#define CMD_CONFIG        0x01u   /* i u16, r u32, h u32 */
#define CMD_TRIGGER       0x02u   /* (no payload) */
#define CMD_QUERY         0x03u   /* (no payload) */
#define CMD_SET_MODE      0x04u   /* mode u8 (MODE_LASER / MODE_ESTIM); refused mid-pulse */
#define CMD_ESTIM_CONFIG  0x05u   /* pulse_dur_ticks u32, ipi_ticks u32 */
#define CMD_LASER_CURRENT 0x06u   /* dac u16: DAC0 code on J9.3 (laser module IREF), 0..LASER_DAC_MAX */
#define CMD_ESTIM_CURRENT 0x07u   /* dac u16: DAC60501 code (e-stim module amplitude), 0..ESTIM_DAC_MAX */
#define CMD_CLEAR_FAULT   0x08u   /* (no payload) clear the latched module fault */
#define CMD_GET_VERSION   0x09u   /* (no payload) -> RSP_VERSION (the one command not
                                     answered with RSP_STATUS; firmware older than
                                     protocol 2 ignores it, which is how the host
                                     tells "old firmware" from "no firmware") */

/* MCU -> Host (responses + events). */
#define RSP_STATUS        0x81u   /* StatusPayload below (34 bytes) */
#define EVT_PULSE_START   0x82u   /* tick u32 */
#define EVT_PULSE_END     0x83u   /* tick u32 */
#define EVT_BUTTON        0x84u   /* mask u8, edges u8 — bit 0 BACK (SW8), bit 1 SELECT
                                     (wheel push), bits 2/3 wheel roll, bit 4 FIRE (SW9),
                                     bit 5 BSL switch (SW6); Rev 2 HAT */
#define EVT_FAULT         0x85u   /* module u8 (flags below), tick u32 — a fault latched */
#define RSP_VERSION       0x86u   /* VersionPayload below (32 bytes), answers CMD_GET_VERSION */

/* Wire-protocol version, reported in RSP_VERSION.proto.  Bump it whenever a
 * payload layout or a message type changes meaning; the broker refuses to
 * trust a firmware whose number differs from its own.  1 = everything before
 * CMD_GET_VERSION existed (v0.2.0-rc1..rc5), 2 = this header. */
#define PROTO_VERSION     2u

/* Phase byte values in RSP_STATUS (ASCII 'W' / 'T'). */
#define PHASE_WAITING     0x57u
#define PHASE_TRIGGERED   0x54u

/* Mode byte values. */
#define MODE_LASER        0x00u
#define MODE_ESTIM        0x01u

/* Module flag bits (StatusPayload.module, EVT_FAULT payload). */
#define MODULE_FAULT_N_LOW    0x01u   /* J8.3 FAULT_n is low right now (fault, or e-stim
                                         isolated side not powered; open on the laser module) */
#define MODULE_FAULT_LATCHED  0x02u   /* a fault edge was caught: outputs locked off,
                                         triggers refused until CMD_CLEAR_FAULT */
#define MODULE_ESTIM_READY    0x04u   /* e-stim DAC60501 acknowledged its GAIN init
                                         (isolated side alive) */
#define MODULE_I2C_ERROR      0x08u   /* the last e-stim DAC write was not acknowledged */
#define MODULE_FLAGS_MASK     0x0Fu

/* EStim parameter limits (100 kHz ticks: 1 tick = 10 µs). */
#define ESTIM_DUR_DEFAULT   10u     /* 100 µs */
#define ESTIM_IPI_DEFAULT   10u     /* 100 µs */
#define ESTIM_DUR_MIN        1u     /* 10 µs */
#define ESTIM_DUR_MAX     1000u     /* 10 ms */
#define ESTIM_IPI_MIN        1u
#define ESTIM_IPI_MAX     1000u

/* DAC code limits.
 *   Laser module: I = V_DAC x (10/49) / 2 ohm with V_DAC = code/4096 x 3.3 V
 *   (VDDA reference) -> 0.0822 mA per code; 3650 ~= 300 mA, the module's
 *   design maximum (red LD max 280 mA).  Default 100 mA.
 *   E-stim module: I = code/4096 x 1.25 V / 2.49 k -> 0.1226 µA per code,
 *   502 µA full scale.  Default 0. */
#define LASER_DAC_MAX      3650u
#define LASER_DAC_DEFAULT  1216u    /* ~100 mA */
#define ESTIM_DAC_MAX      4095u
#define ESTIM_DAC_DEFAULT     0u
#define ADC_CODE_MAX       4095u

/* Inbound (command) payload lengths. */
#define CMD_CONFIG_LEN         10u  /* i(2) + r(4) + h(4) */
#define CMD_SET_MODE_LEN        1u  /* mode(1) */
#define CMD_ESTIM_CONFIG_LEN    8u  /* pulse_dur(4) + ipi(4) */
#define CMD_DAC_LEN             2u  /* dac(2), LASER_CURRENT and ESTIM_CURRENT */

#define PROTO_STATUS_LEN    34u
#define EVT_FAULT_LEN        5u
#define PROTO_VERSION_LEN   32u
#define FW_VERSION_CHARS    30u  /* VersionPayload.version: NUL-padded, not necessarily
                                    NUL-terminated when all 30 are used */

/* Largest payload (inbound or outbound) we assemble or accept. */
#define PROTO_MAX_PAYLOAD   34u

/*
 * Payload structs.  Packed so the wire bytes are exactly the fields in
 * order with no padding, and little-endian — which matches both ends (ARM
 * Cortex-M0+ and the Pi host are LE) and Python's struct formats below.
 * That lets the firmware fill/read a struct and memcpy/cast it to the wire
 * instead of packing bytes by hand.  Reading a received buffer through a
 * packed struct is safe on M0+ (which faults on unaligned access): the
 * compiler emits byte-wise access for the misaligned members.
 *
 * The _Static_asserts lock these to the lengths above; keep them in sync
 * with Pi/protocol.py (_CONFIG = "<HII", _STATUS = "<HIIBBIBIIHHBHH",
 * _VERSION = "<BB30s").
 */
typedef struct __attribute__((packed)) {
    uint16_t intensity;
    uint32_t ramp_ticks;
    uint32_t hold_ticks;
} ConfigPayload;

typedef struct __attribute__((packed)) {
    uint32_t pulse_dur_ticks;
    uint32_t ipi_ticks;
} EstimConfigPayload;

typedef struct __attribute__((packed)) {
    uint16_t dac;
} DacPayload;

typedef struct __attribute__((packed)) {
    uint16_t intensity;
    uint32_t ramp_ticks;
    uint32_t hold_ticks;
    uint8_t  button_mask;
    uint8_t  phase;           /* PHASE_WAITING / PHASE_TRIGGERED */
    uint32_t tick;
    uint8_t  mode;            /* MODE_LASER / MODE_ESTIM */
    uint32_t estim_dur_ticks;
    uint32_t estim_ipi_ticks;
    uint16_t laser_dac;       /* DAC0 code (laser module current setpoint) */
    uint16_t estim_dac;       /* DAC60501 code (e-stim amplitude), as last commanded */
    uint8_t  module;          /* MODULE_* flags */
    uint16_t adc_pd;          /* ADC1.2 (J9.4) raw 12-bit, laser mode only (else 0) */
    uint16_t adc_comp;        /* ADC1.8 (J9.5) raw 12-bit, laser mode only (else 0) */
} StatusPayload;

typedef struct __attribute__((packed)) {
    uint8_t  module;
    uint32_t tick;
} FaultPayload;

/* RSP_VERSION: which firmware is running.  `version` is the build's
 * `git describe` with the leading "v" dropped and "-" turned into "+"
 * (e.g. "0.2.0+rc6", "0.2.0+rc6+3+g1a2b3c4"), i.e. the same string the
 * laserhat Debian package carries in /usr/lib/laserhat/firmware/VERSION,
 * so the broker can compare the two byte for byte. */
typedef struct __attribute__((packed)) {
    uint8_t  proto;                     /* PROTO_VERSION of this firmware */
    uint8_t  reserved;                  /* 0 */
    char     version[FW_VERSION_CHARS]; /* NUL-padded */
} VersionPayload;

_Static_assert(sizeof(ConfigPayload)      == CMD_CONFIG_LEN,      "ConfigPayload layout drift");
_Static_assert(sizeof(EstimConfigPayload) == CMD_ESTIM_CONFIG_LEN, "EstimConfigPayload layout drift");
_Static_assert(sizeof(DacPayload)         == CMD_DAC_LEN,          "DacPayload layout drift");
_Static_assert(sizeof(StatusPayload)      == PROTO_STATUS_LEN,     "StatusPayload layout drift");
_Static_assert(sizeof(FaultPayload)       == EVT_FAULT_LEN,        "FaultPayload layout drift");
_Static_assert(sizeof(VersionPayload)     == PROTO_VERSION_LEN,    "VersionPayload layout drift");

#endif /* PROTOCOL_H */
