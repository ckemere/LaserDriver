# ============================================================
# Laser Driver - MSPM0G3507 — TI ARM CLANG build (workstation)
# ============================================================
# All required SDK files are vendored in-tree:
#   mcu.h                 -> hand-curated MSPM0G3507 device header
#   cmsis/                -> minimal CMSIS Cortex-M0+ core (7 files)
#   hw/                   -> peripheral register layout headers (7 files)
#   startup/              -> ticlang + gcc startup sources
#   linker/               -> ticlang + gcc memory layout

# Tools
CC              := /opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin/tiarmclang

# Paths
PROJ_DIR        := .
BUILD_DIR       := $(PROJ_DIR)/build

# Source files
STARTUP_SRC     := $(PROJ_DIR)/startup/startup_mspm0g350x_ticlang.c
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
INCLUDES        := -I$(PROJ_DIR)
CFLAGS          := $(CPU_FLAGS) $(OPT_FLAGS) $(INCLUDES)

# Linker
LINKER_CMD      := $(PROJ_DIR)/linker/mspm0g3507.cmd
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
