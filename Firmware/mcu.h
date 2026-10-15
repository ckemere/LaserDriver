#ifndef MCU_H
#define MCU_H

/*
 * Hand-curated MSPM0G3507 device header for the LaserHAT firmware.
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
#define UART0_BASE     (0x40108000U)
#define UART1_BASE     (0x40100000U)
#define DAC0_BASE      (0x40018000U)
#define VREF_BASE      (0x40030000U)
#define ADC1_BASE      (0x40002000U)

#define SYSCTL  ((SYSCTL_Regs  *) SYSCTL_BASE)
#define IOMUX   ((IOMUX_Regs   *) IOMUX_BASE)
#define GPIOA   ((GPIO_Regs    *) GPIOA_BASE)
#define TIMA0   ((GPTIMER_Regs *) TIMA0_BASE)
#define TIMG0   ((GPTIMER_Regs *) TIMG0_BASE)
#define TIMG6   ((GPTIMER_Regs *) TIMG6_BASE)
#define UART0   ((UART_Regs    *) UART0_BASE)
#define UART1   ((UART_Regs    *) UART1_BASE)
#define DAC0    ((DAC12_Regs   *) DAC0_BASE)
#define VREF    ((VREF_Regs    *) VREF_BASE)
#define ADC1    ((ADC12_Regs   *) ADC1_BASE)

/* ---------------------------------------------------------------
 * IOMUX PINCM indices for every GPIOA pin of the VQFN-32 package.
 * Source: TI mspm0g350x.h (IOMUX_PINCMn = n-1).  The comment gives
 * the LaserHAT Rev 2 use (see board.h for the authoritative map).
 * --------------------------------------------------------------- */
#define IOMUX_PINCM1   (0u)    /* PA0  — I2C0_SDA (Pi bus, OLED bonnet) */
#define IOMUX_PINCM2   (1u)    /* PA1  — I2C0_SCL */
#define IOMUX_PINCM7   (6u)    /* PA2  — ROSC (R4 100k 0.1 %), analog */
#define IOMUX_PINCM8   (7u)    /* PA3  — spare */
#define IOMUX_PINCM9   (8u)    /* PA4  — spare */
#define IOMUX_PINCM10  (9u)    /* PA5  — spare */
#define IOMUX_PINCM11  (10u)   /* PA6  — DB_GPIO / FAULT_n (J8.3) */
#define IOMUX_PINCM14  (13u)   /* PA7  — DB_PWM_A (J8.5), TIMA0_CCP1 */
#define IOMUX_PINCM19  (18u)   /* PA8  — UART1_TX -> Pi GPIO15 (RXD) */
#define IOMUX_PINCM20  (19u)   /* PA9  — UART1_RX <- Pi GPIO14 (TXD) */
#define IOMUX_PINCM21  (20u)   /* PA10 — UART0_TX -> CH340N */
#define IOMUX_PINCM22  (21u)   /* PA11 — UART0_RX <- CH340N */
#define IOMUX_PINCM34  (33u)   /* PA12 — DB_PWM_B (J8.4), TIMA0_CCP3 */
#define IOMUX_PINCM35  (34u)   /* PA13 — BUTTON4 (SW7 wheel roll) */
#define IOMUX_PINCM36  (35u)   /* PA14 — BUTTON2 (SW7 wheel push) */
#define IOMUX_PINCM37  (36u)   /* PA15 — DB_DAC (J9.3), DAC0_OUT / e-stim RELEASE */
#define IOMUX_PINCM38  (37u)   /* PA16 — BUTTON3 (SW7 wheel roll) */
#define IOMUX_PINCM39  (38u)   /* PA17 — DB_ADC_A (J9.4), ADC1.2 / e-stim I2C SDA */
#define IOMUX_PINCM40  (39u)   /* PA18 — BSL_INVOKE (SW6, active high) */
#define IOMUX_PINCM41  (40u)   /* PA19 — SWDIO <- Pi GPIO25 */
#define IOMUX_PINCM42  (41u)   /* PA20 — SWCLK <- Pi GPIO24 */
#define IOMUX_PINCM46  (45u)   /* PA21 — BUTTON1 (SW8 BACK) */
#define IOMUX_PINCM47  (46u)   /* PA22 — DB_ADC_B (J9.5), ADC1.8 / e-stim I2C SCL */
#define IOMUX_PINCM53  (52u)   /* PA23 — BUTTON5 (SW9 FIRE) */
#define IOMUX_PINCM54  (53u)   /* PA24 — LED_MCU (D7) */
#define IOMUX_PINCM55  (54u)   /* PA25 — MCU_STIM_OUT -> U8 -> J7 BNC + D9 */
#define IOMUX_PINCM59  (58u)   /* PA26 — MCU_STIM_IN <- U8 <- J6 BNC */
#define IOMUX_PINCM60  (59u)   /* PA27 — PI_TRIGGER <- Pi GPIO26 */

/* ---------------------------------------------------------------
 * PINCM peripheral-function codes used by board.h.
 * Source: TI mspm0g350x.h (per-pin PF tables).  Function code 1 is
 * plain GPIO on every PINCM.
 * --------------------------------------------------------------- */
#define IOMUX_PINCM_PF_GPIO                 ((uint32_t)0x00000001U)
#define IOMUX_PINCM11_PF_TIMA_FAULT0        ((uint32_t)0x00000004U)
#define IOMUX_PINCM14_PF_TIMA0_CCP1         ((uint32_t)0x00000008U)
#define IOMUX_PINCM34_PF_TIMA0_CCP3         ((uint32_t)0x00000006U)
#define IOMUX_PINCM19_PF_UART1_TX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM20_PF_UART1_RX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM21_PF_UART0_TX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM22_PF_UART0_RX           ((uint32_t)0x00000002U)
#define IOMUX_PINCM55_PF_TIMG12_CCP1        ((uint32_t)0x00000004U)

#endif /* MCU_H */
