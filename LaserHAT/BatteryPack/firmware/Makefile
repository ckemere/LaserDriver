# BatteryPack rev D charge controller (STM32F042F4P6).  make -> battpack.bin; make flash -> USB DFU:
# hold the BOOT button (SW2) while plugging the board's USB-C into a PC, release, then `make flash` (dfu-util).
# A blank chip boots into DFU by itself (empty flash), so the first flash needs no button.
CC = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
CFLAGS = -mcpu=cortex-m0 -mthumb -Os -Wall -Wextra -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -g
LDFLAGS = -T stm32f042f4.ld -nostdlib -Wl,--gc-sections -Wl,-Map=battpack.map

all: battpack.bin

battpack.elf: main.c startup.c stm32f042f4.ld
	$(CC) $(CFLAGS) main.c startup.c $(LDFLAGS) -o $@
	arm-none-eabi-size $@

battpack.bin: battpack.elf
	$(OBJCOPY) -O binary $< $@

flash: battpack.bin
	dfu-util -a 0 -s 0x08000000:leave -D battpack.bin

clean:
	rm -f battpack.elf battpack.bin battpack.map

.PHONY: all flash clean
