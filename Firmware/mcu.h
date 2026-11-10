#ifndef MCU_H
#define MCU_H

/*
 * Hand-curated MSPM0G3507 / MSPM0G1507 device header for the LaserHAT
 * firmware (Rev 2 HAT = G3507; StimHAT and LaserDriverHAT = G1507, the
 * G3507 without CAN-FD: same RHB pinout, IOMUX, memory map and the
 * peripherals used here).
 *
 * Replaces TI's <ti/devices/msp/msp.h> -> mspm0g350x.h dispatch chain.
 * Defines only the peripheral pointers, IRQ numbers, IOMUX indices and
 * function codes, and CMSIS configuration that this firmware actually
 * uses.  Every value below was copied from TI's mspm0g350x.h
 * (MSPM0 SDK 2.x); pin names are the VQFN-32 (RHB) package.
 *
 * Bit-field definitions and peripheral struct layouts come from the
 * unmodified peripheral headers in hw/ (copies of
 *   sdk/source/ti/devices/msp/peripherals/hw_{gpio,iomux,dac12,vref,adc12,
 *                                              uart,gptimer}.h
 *   sdk/source/ti/devices/msp/peripherals/m0p/sysctl/
 *     hw_sysctl_mspm0g1x0x_g3x0x.h  (renamed hw/hw_sysctl.h here)
 * in the TI MSPM0 SDK 2.10.00.04).
 *
 * To add support for another peripheral: copy its hw_*.h into hw/, add
 * the include below, then add its base address, pointer macro, and IRQ
 * number from TI's mspm0g350x.h.
 */

#include <stdint.h>

/* ---------------------------------------------------------------
 * CMSIS-Core configuration (from TI mspm0g350x.h)
 * --------------------------------------------------------------- */
#define __CM0PLUS_REV           0x0001U
#define __MPU_PRESENT           0x0001U
#define __VTOR_PRESENT          0x0001U
#define __NVIC_PRIO_BITS        0x0002U
#define __Vendor_SysTickConfig  0x0000U

/* ---------------------------------------------------------------
 * IRQ numbers used by this firmware.  Source: TI mspm0g350x.h.
 * System exceptions (-14..-1) are required for CMSIS NVIC inlines.
 * --------------------------------------------------------------- */
typedef enum IRQn
{
  NonMaskableInt_IRQn = -14,
  HardFault_IRQn      = -13,
  SVCall_IRQn         = -5,
  PendSV_IRQn         = -2,
  SysTick_IRQn        = -1,
  GPIOA_INT_IRQn      = 1,    /* shared IRQ 1, handler is GROUP1_IRQHandler */
  UART1_INT_IRQn      = 13,   /* Pi UART (PA8/PA9) */
  UART0_INT_IRQn      = 15,   /* USB-C UART via CH340N (PA10/PA11) */
  TIMG0_INT_IRQn      = 16,
  TIMG6_INT_IRQn      = 17,
  TIMA0_INT_IRQn      = 18,
} IRQn_Type;

#include "cmsis/core_cm0plus.h"

/* ---------------------------------------------------------------
 * Peripheral register layouts and bit definitions
 * (hw/ files vendored unmodified from the TI SDK).
 * --------------------------------------------------------------- */
#include "hw/hw_gpio.h"
#include "hw/hw_iomux.h"
#include "hw/hw_dac12.h"
#include "hw/hw_vref.h"
#include "hw/hw_adc12.h"
#include "hw/hw_uart.h"
#include "hw/hw_gptimer.h"
#include "hw/hw_sysctl.h"

/* ---------------------------------------------------------------
 * Peripheral base addresses and pointers.  Source: TI mspm0g350x.h.
 * --------------------------------------------------------------- */
#define SYSCTL_BASE    (0x400AF000U)
#define IOMUX_BASE     (0x40428000U)
#define GPIOA_BASE     (0x400A0000U)
#define TIMA0_BASE     (0x40860000U)
#define TIMG0_BASE     (0x40084000U)
#define TIMG6_BASE     (0x40868000U)
#define TIMG7_BASE     (0x4086A000U)   /* LaserDriverHAT PWM; SLASEW9E table 8-6 */
#define UART0_BASE     (0x40108000U)
#define UART1_BASE     (0x40100000U)
#define DAC0_BASE      (0x40018000U)
#define VREF_BASE      (0x40030000U)
#define ADC0_BASE      (0x40000000U)   /* LaserDriverHAT (also SLASEW9E table 8-6) */
#define ADC1_BASE      (0x40002000U)

#define SYSCTL  ((SYSCTL_Regs  *) SYSCTL_BASE)
#define IOMUX   ((IOMUX_Regs   *) IOMUX_BASE)
#define GPIOA   ((GPIO_Regs    *) GPIOA_BASE)
#define TIMA0   ((GPTIMER_Regs *) TIMA0_BASE)
#define TIMG0   ((GPTIMER_Regs *) TIMG0_BASE)
#define TIMG6   ((GPTIMER_Regs *) TIMG6_BASE)
#define TIMG7   ((GPTIMER_Regs *) TIMG7_BASE)
#define UART0   ((UART_Regs    *) UART0_BASE)
#define UART1   ((UART_Regs    *) UART1_BASE)
#define DAC0    ((DAC12_Regs   *) DAC0_BASE)
#define VREF    ((VREF_Regs    *) VREF_BASE)
#define ADC0    ((ADC12_Regs   *) ADC0_BASE)
#define ADC1    ((ADC12_Regs   *) ADC1_BASE)

/* ---------------------------------------------------------------
 * IOMUX PINCM indices for every GPIOA pin of the VQFN-32 package.
 * Source: TI mspm0g350x.h (IOMUX_PINCMn = n-1); PINCMx per pin checked
 * against the MSPM0G1507 datasheet SLASEW9E table 6-2 (shared RHB pinout).
 * Use per board (R = Rev 2, S = StimHAT, L = LaserDriverHAT; board_*.h
 * are authoritative).
 * --------------------------------------------------------------- */
#define IOMUX_PINCM1   (0u)    /* PA0  — I2C0_SDA, Pi bus (all: never driven) */
#define IOMUX_PINCM2   (1u)    /* PA1  — I2C0_SCL, Pi bus (all: never driven) */
#define IOMUX_PINCM7   (6u)    /* PA2  — ROSC, analog (all) */
#define IOMUX_PINCM8   (7u)    /* PA3  — spare (all) */
#define IOMUX_PINCM9   (8u)    /* PA4  — R spare; S/L PI_TRIGGER */
#define IOMUX_PINCM10  (9u)    /* PA5  — R spare; S/L LED_MCU */
#define IOMUX_PINCM11  (10u)   /* PA6  — R FAULT_n (J8.3); S spare; L BUTTON1 */
#define IOMUX_PINCM14  (13u)   /* PA7  — R DB_PWM_A TIMA0_CCP1; S/L BUTTON4 */
#define IOMUX_PINCM19  (18u)   /* PA8  — UART1_TX -> Pi (all) */
#define IOMUX_PINCM20  (19u)   /* PA9  — UART1_RX <- Pi (all) */
#define IOMUX_PINCM21  (20u)   /* PA10 — UART0_TX -> CH340N (all) */
#define IOMUX_PINCM22  (21u)   /* PA11 — UART0_RX <- CH340N (all) */
#define IOMUX_PINCM34  (33u)   /* PA12 — R DB_PWM_B TIMA0_CCP3; S BUTTON1; L BUTTON6 */
#define IOMUX_PINCM35  (34u)   /* PA13 — R BUTTON4; S BUTTON6; L BUTTON2 */
#define IOMUX_PINCM36  (35u)   /* PA14 — R/S BUTTON2; L BUTTON3 */
#define IOMUX_PINCM37  (36u)   /* PA15 — R DB_DAC / RELEASE; S BUTTON3; L DB_DAC (DAC0_OUT) */
#define IOMUX_PINCM38  (37u)   /* PA16 — R BUTTON3; S/L BUTTON5 FIRE */
#define IOMUX_PINCM39  (38u)   /* PA17 — R DB_ADC_A (A1_2) / SDA; S/L MCU_STIM_OUT */
#define IOMUX_PINCM40  (39u)   /* PA18 — BSL_INVOKE (all) */
#define IOMUX_PINCM41  (40u)   /* PA19 — SWDIO (all) */
#define IOMUX_PINCM42  (41u)   /* PA20 — SWCLK (all) */
#define IOMUX_PINCM46  (45u)   /* PA21 — R BUTTON1; S/L MCU_STIM_IN */
#define IOMUX_PINCM47  (46u)   /* PA22 — R DB_ADC_B / SCL; S FAULT_H; L spare */
#define IOMUX_PINCM53  (52u)   /* PA23 — R BUTTON5; S CATH_H; L spare */
#define IOMUX_PINCM54  (53u)   /* PA24 — R LED_MCU; S EN_H; L DB_ADC_B (A0_3) */
#define IOMUX_PINCM55  (54u)   /* PA25 — R MCU_STIM_OUT; S RELEASE_H; L DB_ADC_A (A0_2) */
#define IOMUX_PINCM59  (58u)   /* PA26 — R MCU_STIM_IN; S SDA_H; L DB_PWM_A TIMG7_C0 */
#define IOMUX_PINCM60  (59u)   /* PA27 — R PI_TRIGGER; S SCL_H; L DB_PWM_B TIMG7_C1 */

/* ---------------------------------------------------------------
 * PINCM peripheral-function codes used by the board headers.
 * Source: TI mspm0g350x.h (per-pin PF tables); the codes added for the
 * StimHAT / LaserDriverHAT were taken from SLASEW9E table 6-2 (the
 * "[n]" after each digital function is its PF code).  Function code 1 is
 * plain GPIO on every PINCM.
 * --------------------------------------------------------------- */
#define IOMUX_PINCM_PF_GPIO                 ((uint32_t)0x00000001U)
#define IOMUX_PINCM11_PF_TIMA_FAULT0        ((uint32_t)0x00000004U)
#define IOMUX_PINCM14_PF_TIMA0_CCP1         ((uint32_t)0x00000008U)
#define IOMUX_PINCM34_PF_TIMA0_CCP3         ((uint32_t)0x00000006U)
#define IOMUX_PINCM59_PF_TIMG7_CCP0         ((uint32_t)0x00000007U)   /* PA26 TIMG7_C0 [7], table 6-2 (L) */
#define IOMUX_PINCM60_PF_TIMG7_CCP1         ((uint32_t)0x00000007U)   /* PA27 TIMG7_C1 [7], table 6-2 (L) */
#define IOMUX_PINCM19_PF_UART1_TX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM20_PF_UART1_RX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM21_PF_UART0_TX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM22_PF_UART0_RX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM55_PF_TIMG12_CCP1        ((uint32_t)0x00000004U)

#endif /* MCU_H */
