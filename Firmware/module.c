#include "module.h"
#include "board.h"
#include "mcu.h"

/* ---------------------------------------------------------------------
 * IOMUX roles
 * --------------------------------------------------------------------- */

#define PINCM_ANALOG      0u      /* reset default: no digital function */
#define PINCM_GPIO_OUT    (IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO)
#define PINCM_GPIO_OD     (IOMUX_PINCM_PC_CONNECTED | IOMUX_PINCM_PF_GPIO | \
                           IOMUX_PINCM_INENA_ENABLE | IOMUX_PINCM_HIZ1_ENABLE | \
                           IOMUX_PINCM_PIPU_ENABLE)

#define J9_PINS  (BOARD_DAC_PIN | BOARD_ADC_A_PIN | BOARD_ADC_B_PIN)

void module_laser_pins(void)
{
    /* Drop the GPIO drivers first, then disconnect: a DOUT of 1 on the
     * open-drain pins means "released", so nothing glitches low. */
    BOARD_GPIO_PORT->DOECLR31_0 = J9_PINS;
    IOMUX->SECCFG.PINCM[BOARD_DAC_PINCM]   = PINCM_ANALOG;
    IOMUX->SECCFG.PINCM[BOARD_ADC_A_PINCM] = PINCM_ANALOG;
    IOMUX->SECCFG.PINCM[BOARD_ADC_B_PINCM] = PINCM_ANALOG;
}

void module_estim_pins(void)
{
    /* RELEASE low (electrode shorted), SDA/SCL released (DOUT 1 = Hi-Z). */
    BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_ESTIM_RELEASE_PIN;
    BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_ESTIM_SDA_PIN | BOARD_ESTIM_SCL_PIN;
    IOMUX->SECCFG.PINCM[BOARD_DAC_PINCM]       = PINCM_GPIO_OUT;
    IOMUX->SECCFG.PINCM[BOARD_ESTIM_SDA_PINCM] = PINCM_GPIO_OD;
    IOMUX->SECCFG.PINCM[BOARD_ESTIM_SCL_PINCM] = PINCM_GPIO_OD;
    BOARD_GPIO_PORT->DOESET31_0 = J9_PINS;
}

/* ---------------------------------------------------------------------
 * Bit-banged I2C master (SDA = PA17, SCL = PA22, open-drain)
 * --------------------------------------------------------------------- */

/* Half a bit at ~200 kHz: ~2.5 µs = 80 cycles at 32 MHz.  The loop body is
 * ~3 cycles per iteration. */
#define I2C_HALF_BIT_LOOPS   28u
#define I2C_STRETCH_LIMIT    2000u

static void i2c_delay(void)
{
    volatile uint32_t i = I2C_HALF_BIT_LOOPS;
    while (i--) { /* nop */ }
}

static inline void sda_release(void) { BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_ESTIM_SDA_PIN; }
static inline void sda_low(void)     { BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_ESTIM_SDA_PIN; }
static inline void scl_release(void) { BOARD_GPIO_PORT->DOUTSET31_0 = BOARD_ESTIM_SCL_PIN; }
static inline void scl_low(void)     { BOARD_GPIO_PORT->DOUTCLR31_0 = BOARD_ESTIM_SCL_PIN; }
static inline bool sda_read(void)    { return (BOARD_GPIO_PORT->DIN31_0 & BOARD_ESTIM_SDA_PIN) != 0u; }
static inline bool scl_read(void)    { return (BOARD_GPIO_PORT->DIN31_0 & BOARD_ESTIM_SCL_PIN) != 0u; }

/* Release SCL and wait for it to actually rise (clock stretching / pull-up
 * check).  false when nothing pulls the line up (no module). */
static bool scl_high(void)
{
    scl_release();
    for (uint32_t n = 0; n < I2C_STRETCH_LIMIT; n++) {
        if (scl_read()) {
            return true;
        }
    }
    return false;
}

static bool i2c_start(void)
{
    sda_release();
    if (!scl_high()) {
        return false;
    }
    i2c_delay();
    if (!sda_read()) {
        return false;                   /* bus held low: no pull-ups / stuck slave */
    }
    sda_low();                          /* START: SDA falls while SCL high */
    i2c_delay();
    scl_low();
    i2c_delay();
    return true;
}

static void i2c_stop(void)
{
    sda_low();
    i2c_delay();
    (void)scl_high();
    i2c_delay();
    sda_release();                      /* STOP: SDA rises while SCL high */
    i2c_delay();
}

/* Shift one byte out MSB first; true when the slave acknowledged. */
static bool i2c_write_byte(uint8_t b)
{
    for (int bit = 7; bit >= 0; bit--) {
        if (b & (1u << bit)) {
            sda_release();
        } else {
            sda_low();
        }
        i2c_delay();
        if (!scl_high()) {
            return false;
        }
        i2c_delay();
        scl_low();
    }
    /* ACK clock: release SDA, sample while SCL high. */
    sda_release();
    i2c_delay();
    if (!scl_high()) {
        return false;
    }
    i2c_delay();
    bool ack = !sda_read();
    scl_low();
    i2c_delay();
    return ack;
}

static bool i2c_write(uint8_t addr7, const uint8_t *data, uint32_t len)
{
    bool ok = i2c_start();
    if (ok) {
        ok = i2c_write_byte((uint8_t)(addr7 << 1));   /* write */
        for (uint32_t i = 0; ok && i < len; i++) {
            ok = i2c_write_byte(data[i]);
        }
    }
    i2c_stop();
    return ok;
}

/* ---------------------------------------------------------------------
 * DAC60501 (spec §7): frame = address 0x90 · command · MSB · LSB
 * --------------------------------------------------------------------- */

#define DAC60501_ADDR      0x48u
#define DAC60501_REG_GAIN  0x04u
#define DAC60501_REG_DAC   0x08u

bool module_estim_dac_init(void)
{
    /* GAIN = 0x0100: REF-DIV = 1, BUFF-GAIN = 0 -> 0..1.25 V full scale.
     * The power-on default (gain 2) would give 4x the intended current. */
    const uint8_t frame[3] = { DAC60501_REG_GAIN, 0x01u, 0x00u };
    return i2c_write(DAC60501_ADDR, frame, 3u);
}

bool module_estim_dac_write(uint16_t code12)
{
    uint16_t v = (uint16_t)((code12 & 0x0FFFu) << 4);
    const uint8_t frame[3] = { DAC60501_REG_DAC, (uint8_t)(v >> 8), (uint8_t)(v & 0xFFu) };
    return i2c_write(DAC60501_ADDR, frame, 3u);
}
