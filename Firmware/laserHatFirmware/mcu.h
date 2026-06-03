#ifndef MCU_H
#define MCU_H

/*
 * Hand-curated MSPM0G3507 device header for the LaserHAT firmware.
 *
 * Replaces TI's <ti/devices/msp/msp.h> -> mspm0g350x.h dispatch chain.
 * Defines only the peripheral pointers, IRQ numbers, IOMUX function
 * codes, and CMSIS configuration that this firmware actually uses.
 *
 * Bit-field definitions and peripheral struct layouts come from the
 * unmodified peripheral headers in hw/ (which themselves are copies
 * of:
 *   sdk/source/ti/devices/msp/peripherals/hw_{gpio,iomux,dac12,vref,
 *                                              uart,gptimer}.h
 *   sdk/source/ti/devices/msp/peripherals/m0p/sysctl/
 *     hw_sysctl_mspm0g1x0x_g3x0x.h  (renamed hw/hw_sysctl.h here)
 * in the TI MSPM0 SDK 2.10.00.04).
 *
 * To add support for another peripheral on the chip: copy its
 * hw_*.h into hw/, add the include below, then add its base address,
 * pointer macro, and IRQ number from TI's mspm0g350x.h.
 */

#include <stdint.h>

/* ---------------------------------------------------------------
 * CMSIS-Core configuration (from TI mspm0g350x.h: __CM0PLUS_REV,
 * __MPU_PRESENT, __VTOR_PRESENT, __NVIC_PRIO_BITS, __Vendor_*)
 * --------------------------------------------------------------- */
#define __CM0PLUS_REV           0x0001U
#define __MPU_PRESENT           0x0001U
#define __VTOR_PRESENT          0x0001U
#define __NVIC_PRIO_BITS        0x0002U
#define __Vendor_SysTickConfig  0x0000U

/* ---------------------------------------------------------------
 * IRQ numbers used by this firmware.  Source: TI mspm0g350x.h.
 * Add more here if you wire additional peripherals into IRQ
 * handlers.  System exceptions (-14..-1) are required for CMSIS
 * NVIC inlines; the user IRQs below cover only what we use.
 * --------------------------------------------------------------- */
typedef enum IRQn
{
  NonMaskableInt_IRQn = -14,
  HardFault_IRQn      = -13,
  SVCall_IRQn         = -5,
  PendSV_IRQn         = -2,
  SysTick_IRQn        = -1,
  UART0_INT_IRQn      = 15,
  TIMG0_INT_IRQn      = 16,
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
#include "hw/hw_uart.h"
#include "hw/hw_gptimer.h"
#include "hw/hw_sysctl.h"

/* ---------------------------------------------------------------
 * Peripheral base addresses and pointers.  Source: TI mspm0g350x.h.
 * Only the peripherals this firmware uses are exposed.
 * --------------------------------------------------------------- */
#define SYSCTL_BASE    (0x400AF000U)
#define IOMUX_BASE     (0x40428000U)
#define GPIOA_BASE     (0x400A0000U)
#define TIMA0_BASE     (0x40860000U)
#define TIMG0_BASE     (0x40084000U)
#define UART0_BASE     (0x40108000U)
#define DAC0_BASE      (0x40018000U)
#define VREF_BASE      (0x40030000U)

#define SYSCTL  ((SYSCTL_Regs  *) SYSCTL_BASE)
#define IOMUX   ((IOMUX_Regs   *) IOMUX_BASE)
#define GPIOA   ((GPIO_Regs    *) GPIOA_BASE)
#define TIMA0   ((GPTIMER_Regs *) TIMA0_BASE)
#define TIMG0   ((GPTIMER_Regs *) TIMG0_BASE)
#define UART0   ((UART_Regs    *) UART0_BASE)
#define DAC0    ((DAC12_Regs   *) DAC0_BASE)
#define VREF    ((VREF_Regs    *) VREF_BASE)

/* ---------------------------------------------------------------
 * IOMUX PINCM indices used in board.h.  Source: TI mspm0g350x.h
 * (IOMUX_PINCMn = (n-1)).  Only the ones our firmware references.
 * --------------------------------------------------------------- */
#define IOMUX_PINCM1   (0u)    /* PA0  — unused, gpio-driven low */
#define IOMUX_PINCM2   (1u)    /* PA1  — unused */
#define IOMUX_PINCM7   (6u)    /* PA2  — unused */
#define IOMUX_PINCM8   (7u)    /* PA3  — BUTTON1 */
#define IOMUX_PINCM9   (8u)    /* PA4  — unused */
#define IOMUX_PINCM10  (9u)    /* PA5  — unused */
#define IOMUX_PINCM11  (10u)   /* PA6  — unused */
#define IOMUX_PINCM14  (13u)   /* PA7  — unused */
#define IOMUX_PINCM19  (18u)   /* PA8  — unused */
#define IOMUX_PINCM20  (19u)   /* PA9  — unused */
#define IOMUX_PINCM21  (20u)   /* PA10 — UART0 TX */
#define IOMUX_PINCM22  (21u)   /* PA11 — UART0 RX */
#define IOMUX_PINCM34  (33u)   /* PA12 — unused */
#define IOMUX_PINCM35  (34u)   /* PA13 — STIM_MIRROR LED */
#define IOMUX_PINCM36  (35u)   /* PA14 — unused */
#define IOMUX_PINCM37  (36u)   /* PA15 — DAC OUT */
#define IOMUX_PINCM38  (37u)   /* PA16 — unused */
#define IOMUX_PINCM39  (38u)   /* PA17 — unused */
#define IOMUX_PINCM40  (39u)   /* PA18 — unused */
#define IOMUX_PINCM46  (45u)   /* PA21 — PWM_LASER (TIMA0_CCP0) */
#define IOMUX_PINCM47  (46u)   /* PA22 — PWM_DUMMY (TIMA0_CCP0_CMPL) */
#define IOMUX_PINCM48  (47u)   /* PA23 — VREF+ */
#define IOMUX_PINCM54  (53u)   /* PA24 — unused */
#define IOMUX_PINCM55  (54u)   /* PA25 — unused */
#define IOMUX_PINCM59  (58u)   /* PA26 — unused */
#define IOMUX_PINCM60  (59u)   /* PA27 — unused */

/* ---------------------------------------------------------------
 * PINCM peripheral-function codes used by board.h.
 * Source: TI mspm0g350x.h (per-pin PF tables).  Only the codes our
 * firmware actually selects are defined; every PINCM also accepts
 * function code 1 to mean plain GPIO, written directly as 0x1u in
 * laser_gpio.c.
 * --------------------------------------------------------------- */
#define IOMUX_PINCM8_PF_GPIOA_DIO3      ((uint32_t)0x00000001U)
#define IOMUX_PINCM35_PF_GPIOA_DIO13    ((uint32_t)0x00000001U)
#define IOMUX_PINCM46_PF_GPIOA_DIO21    ((uint32_t)0x00000001U)
#define IOMUX_PINCM46_PF_TIMA0_CCP0     ((uint32_t)0x00000005U)
#define IOMUX_PINCM47_PF_GPIOA_DIO22    ((uint32_t)0x00000001U)
#define IOMUX_PINCM47_PF_TIMA0_CCP0_CMPL ((uint32_t)0x00000007U)
#define IOMUX_PINCM21_PF_UART0_TX       ((uint32_t)0x00000002U)
#define IOMUX_PINCM22_PF_UART0_RX       ((uint32_t)0x00000002U)

#endif /* MCU_H */
