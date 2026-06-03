# ============================================================
# Laser Driver - MSPM0G3507 — TI ARM CLANG build (workstation)
# ============================================================
# SDK headers/startup/linker are vendored under ./sdk so this build
# has no external SDK path dependency.  Only the tiarmclang toolchain
# itself is external.  See Makefile.gcc for the Pi-native arm-none-eabi
# build with no TI tooling at all.

# Tools
CC              := /opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin/tiarmclang

# Paths
PROJ_DIR        := .
SDK_DIR         := $(PROJ_DIR)/sdk
BUILD_DIR       := $(PROJ_DIR)/build

# Source files
STARTUP_SRC     := $(SDK_DIR)/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c
STARTUP_OBJ     := $(BUILD_DIR)/startup_mspm0g350x_ticlang.o

OBJS            := $(BUILD_DIR)/laser_driver.o \
                   $(BUILD_DIR)/laser_pwm_control.o \
                   $(BUILD_DIR)/laser_sysctl.o \
                   $(BUILD_DIR)/laser_gpio.o \
                   $(BUILD_DIR)/laser_timera.o \
                   $(BUILD_DIR)/laser_timerg.o \
                   $(BUILD_DIR)/laser_dac.o \
                   $(BUILD_DIR)/laser_uart.o \
                   $(STARTUP_OBJ)

# Compiler flags
CPU_FLAGS       := -mcpu=cortex-m0plus -mthumb
OPT_FLAGS       := -O0 -g
DEVICE_DEFS     := -D__MSPM0G3507__
INCLUDES        := \
    -I$(SDK_DIR)/source \
    -I$(SDK_DIR)/source/ti/devices/msp \
    -I$(SDK_DIR)/source/ti/devices/msp/m0p \
    -I$(SDK_DIR)/source/third_party/CMSIS/Core/Include

CFLAGS          := $(CPU_FLAGS) $(OPT_FLAGS) $(DEVICE_DEFS) $(INCLUDES)

# Linker flags
LINKER_CMD      := $(SDK_DIR)/source/ti/devices/msp/m0p/linker_files/ticlang/mspm0g3507.cmd
LFLAGS          := -Wl,--rom_model \
                   -Wl,-m,$(BUILD_DIR)/laser_driver.map \
                   -T$(LINKER_CMD)

# Output
TARGET          := $(BUILD_DIR)/laser_driver.out

# ============================================================

.PHONY: all clean

all: $(TARGET)
	@echo "Build complete: $(TARGET)"

$(TARGET): $(OBJS) | $(BUILD_DIR)
	$(CC) $(CPU_FLAGS) $(OBJS) $(LFLAGS) -o $@

$(BUILD_DIR)/%.o: $(PROJ_DIR)/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(STARTUP_OBJ): $(STARTUP_SRC) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)
