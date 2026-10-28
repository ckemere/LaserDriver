/*
 * BatteryPack rev D charge controller: STM32F042F4P6 on the floating charger island (powered from VBUS, so it only
 * exists while a USB-C source is plugged in).  It owns the CN3704's power (CHG_EN -> Q12 / Q13), the relay that
 * connects the charger to pack A (released) or pack B (energised), and the four status LEDs.
 *
 * Pins (TSSOP-20):  PA0 ADC_IN0 VBAT_S (the connected pack, 118/18 divider)   PA1 ADC_IN1 VBUS_S (118/18)
 *                   PA2 CHRG_n (CN3704, open drain, 10k up)  PA3 DONE_n       PA4 RELAY (high = pack B)
 *                   PA5 CHG_EN (high = charger powered)      PA6 LED pack A charging (red)   PA7 LED pack A done (green)
 *                   PB1 LED pack B charging                  PF0 LED pack B done
 *
 * Algorithm ("charge the lower pack"):
 *   1. source present and >= 15 V (a PD brick, not a PC port): connect A, read it at rest, connect B, read it; a pack
 *      below 9 V is absent.  Start on the lower present pack.
 *   2. charge in slots of SLOT_S seconds with the charger power-cycled at every (re)connection, so the CN3704 starts
 *      a fresh cycle even on a pack above its 16.0 V recharge threshold.  DONE asserted for 2 s flags the pack full;
 *      a pack that is neither charging nor done 5 s after power-up (over-voltage, NTC fault, not there) is treated as
 *      full for this session.
 *   3. at the end of a slot: charger off, 1 s rest, read the connected pack, swap to the other pack if that one is not
 *      full and its last resting reading is lower by more than SWAP_MV; a flagged pack is never reconnected.
 *   4. both full (or absent): charger off, K2 open (island off the packs), both DONE LEDs on.
 * K1 (pack A / B) only moves with the charger off and K2 (LINK, both poles of the island's +CHG / CGND) open, so the
 * island is never tied to a pack half-way through K1's transfer; K2 then closes and the charger restarts.  The IWDG
 * resets the MCU if the loop ever stalls; in reset / DFU both coils are off (pull-downs), i.e. the island is isolated.
 *
 * Bare metal, HSI 8 MHz, SysTick 1 ms, no USB in the application (the ROM DFU bootloader does the flashing).
 */
#include <stdint.h>

#define REG(a) (*(volatile uint32_t *)(a))
#define RCC_AHBENR  REG(0x40021014)
#define RCC_APB2ENR REG(0x40021018)
#define RCC_CSR     REG(0x40021024)
#define GPIOA 0x48000000
#define GPIOB 0x48000400
#define GPIOF 0x48001400
#define MODER(g)  REG((g) + 0x00)
#define PUPDR(g)  REG((g) + 0x0C)
#define IDR(g)    REG((g) + 0x10)
#define BSRR(g)   REG((g) + 0x18)
#define ADC_ISR    REG(0x40012400)
#define ADC_CR     REG(0x40012408)
#define ADC_CFGR1  REG(0x4001240C)
#define ADC_CFGR2  REG(0x40012410)
#define ADC_SMPR   REG(0x40012414)
#define ADC_CHSELR REG(0x40012428)
#define ADC_DR     REG(0x40012440)
#define IWDG_KR  REG(0x40003000)
#define IWDG_PR  REG(0x40003004)
#define IWDG_RLR REG(0x40003008)
#define IWDG_SR  REG(0x4000300C)
#define SYST_CSR  REG(0xE000E010)
#define SYST_RVR  REG(0xE000E014)
#define SYST_CVR  REG(0xE000E018)

enum { PIN_VBAT = 0, PIN_VBUS = 1, PIN_CHRG = 2, PIN_DONE = 3, PIN_RELAY = 4, PIN_CHG_EN = 5, PIN_LED_CA = 6, PIN_LED_DA = 7 };
#define PIN_LED_CB 1      /* PB1 */
#define PIN_LED_DB 0      /* PF0 */
#define PIN_LINK   1      /* PF1: K2, both poles of the island's +CHG / CGND; open while K1 moves */

#define SLOT_S      180   /* seconds per charging slot before the packs are compared again */
#define SWAP_MV      50   /* swap when the other pack rests this much lower */
#define BRICK_MV  18000   /* below this the source is a PC port (DFU) or a weak charger: do nothing (the 12 V coils need > 15 V on VBUS) */
#define ABSENT_MV  9000   /* a pack reading below this is not there (or beyond saving) */
#define DONE_MS    2000   /* DONE must be asserted this long */
#define SILENT_MS  5000   /* neither CHRG nor DONE this long after power-up = the IC refuses this pack */

static volatile uint32_t ms;

void SysTick_Handler(void) { ms++; }

static void delay(uint32_t d) { uint32_t t = ms; while (ms - t < d) { IWDG_KR = 0xAAAA; } }
static void kick(void) { IWDG_KR = 0xAAAA; }

static void pin_set(uint32_t g, int p, int on) { BSRR(g) = on ? (1u << p) : (1u << (p + 16)); }
static int pin_get(uint32_t g, int p) { return (IDR(g) >> p) & 1; }

static void gpio_init(void)
{
    RCC_AHBENR |= (1u << 17) | (1u << 18) | (1u << 22);          /* IOPA, IOPB, IOPF */
    /* PA0 / PA1 analog (11), PA2 / PA3 input (00), PA4-PA7 output (01) */
    MODER(GPIOA) = (MODER(GPIOA) & ~0x0000FFFFu) | 0x0000550Fu;
    MODER(GPIOB) = (MODER(GPIOB) & ~(3u << (2 * PIN_LED_CB))) | (1u << (2 * PIN_LED_CB));
    MODER(GPIOF) = (MODER(GPIOF) & ~((3u << (2 * PIN_LED_DB)) | (3u << (2 * PIN_LINK)))) | (1u << (2 * PIN_LED_DB)) | (1u << (2 * PIN_LINK));
    PUPDR(GPIOA) &= ~0x000000F0u;                                 /* CHRG / DONE: external 10k pull-ups */
}

static void adc_init(void)
{
    RCC_APB2ENR |= (1u << 9);
    ADC_CFGR2 = 1u << 30;                                         /* PCLK / 2 = 4 MHz */
    ADC_CR |= (1u << 31);                                         /* ADCAL */
    while (ADC_CR & (1u << 31)) {}
    ADC_ISR |= 1u;                                                /* clear ADRDY */
    ADC_CR |= 1u;                                                 /* ADEN */
    while (!(ADC_ISR & 1u)) {}
    ADC_SMPR = 7;                                                 /* 239.5 cycles: the 100k dividers are slow */
    ADC_CFGR1 = 0;                                                /* 12 bit, single, right aligned */
}

static uint32_t adc_read(int ch)
{
    uint32_t sum = 0;
    ADC_CHSELR = 1u << ch;
    for (int i = 0; i < 16; i++) {
        ADC_CR |= (1u << 2);                                      /* ADSTART */
        while (!(ADC_ISR & (1u << 2))) {}
        sum += ADC_DR;                                            /* reading DR clears EOC */
    }
    return sum / 16;
}

/* millivolts at the top of a 100k / 18k divider from a 12-bit reading against 3.3 V: raw * 3300 * 118 / 18 / 4095 */
static uint32_t mv(int ch) { return adc_read(ch) * 21633u / 4095u; }

static void charger(int on) { pin_set(GPIOA, PIN_CHG_EN, on); }
static void link(int on) { pin_set(GPIOF, PIN_LINK, on); }
/* move K1 only with the island isolated: open K2, wait for its contacts, move K1, wait, close K2 (G6S-2 operate / release 5 ms max) */
static void relay(int pack_b)
{
    static int current = -1;
    if (pack_b == current) { link(1); return; }
    link(0); delay(30);
    pin_set(GPIOA, PIN_RELAY, pack_b); delay(30);
    link(1); delay(30);
    current = pack_b;
}
static void leds(int ca, int da, int cb, int db)
{
    pin_set(GPIOA, PIN_LED_CA, ca); pin_set(GPIOA, PIN_LED_DA, da);
    pin_set(GPIOB, PIN_LED_CB, cb); pin_set(GPIOF, PIN_LED_DB, db);
}

/* connect a pack with the charger off (dry switching), let the node settle, read it at rest */
static uint32_t connect_and_read(int pack)
{
    charger(0);
    delay(300);
    relay(pack);
    delay(300);
    return mv(PIN_VBAT);
}

int main(void)
{
    gpio_init();
    adc_init();
    SYST_RVR = 8000 - 1; SYST_CVR = 0; SYST_CSR = 7;              /* 1 ms at 8 MHz HSI */
    RCC_CSR |= 1u;                                                /* LSI on for the IWDG */
    IWDG_KR = 0xCCCC; IWDG_KR = 0x5555; IWDG_PR = 4; IWDG_RLR = 2500;   /* /64: 625 Hz -> 4 s */
    while (IWDG_SR) {}
    IWDG_KR = 0xAAAA;

    int done[2] = {0, 0};
    uint32_t rest[2] = {0, 0};
    charger(0); link(0); leds(0, 0, 0, 0);

    /* not a brick: blink both charging LEDs slowly (DFU / weak source), never charge */
    while (mv(PIN_VBUS) < BRICK_MV) {
        leds(1, 0, 1, 0); delay(100); leds(0, 0, 0, 0); delay(1900);
    }
    rest[0] = connect_and_read(0);
    rest[1] = connect_and_read(1);
    for (int p = 0; p < 2; p++) if (rest[p] < ABSENT_MV) done[p] = 1;
    int sel = (rest[1] < rest[0]) ? 1 : 0;
    if (done[sel]) sel ^= 1;

    for (;;) {
        kick();
        if (done[0] && done[1]) {                                 /* both full or absent: idle */
            charger(0); link(0);                                  /* island off the packs: no idle drain, nothing lifted by leakage */
            leds(0, rest[0] >= ABSENT_MV, 0, rest[1] >= ABSENT_MV);
            delay(500);
            continue;
        }
        /* one slot on the selected pack */
        relay(sel); delay(100); charger(1);
        uint32_t t0 = ms, done_since = 0, active_seen = 0;
        int flag_done = 0;
        while (ms - t0 < SLOT_S * 1000u) {
            kick();
            int chrg = !pin_get(GPIOA, PIN_CHRG), dn = !pin_get(GPIOA, PIN_DONE);
            if (chrg || dn) active_seen = 1;
            leds(sel == 0 && chrg, done[0], sel == 1 && chrg, done[1]);
            if (dn) { if (!done_since) done_since = ms; if (ms - done_since >= DONE_MS) { flag_done = 1; break; } }
            else done_since = 0;
            if (!active_seen && ms - t0 >= SILENT_MS) { flag_done = 1; break; }
            delay(20);
        }
        charger(0);
        delay(1000);                                              /* rest, then read the connected pack */
        rest[sel] = mv(PIN_VBAT);
        if (flag_done) done[sel] = 1;
        int other = sel ^ 1;
        if (done[sel] || (!done[other] && rest[other] + SWAP_MV < rest[sel])) {
            if (!done[other]) sel = other;
        }
    }
}
