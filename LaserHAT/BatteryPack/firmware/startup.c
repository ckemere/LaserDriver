/* minimal Cortex-M0 start-up for the STM32F042: vector table, .data copy, .bss clear */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern int main(void);
void SysTick_Handler(void);

void Reset_Handler(void)
{
    uint32_t *src = &_sidata, *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss;) *dst++ = 0;
    main();
    for (;;) {}
}

static void Default_Handler(void) { for (;;) {} }

__attribute__((section(".isr_vector"), used))
const void *const vectors[16 + 32] = {
    &_estack, Reset_Handler, Default_Handler, Default_Handler, 0, 0, 0, 0, 0, 0, 0,
    Default_Handler, 0, 0, Default_Handler, SysTick_Handler,
    /* 32 peripheral interrupts, none used */
};
