# ============================================================
# Laser Driver - MSPM0G3507
# ============================================================

# Tools
SDK_ROOT        := /opt/ti/mspm0_sdk_2_10_00_04
SYSCONFIG_ROOT  := /opt/ti/sysconfig_1.27.0
CC              := /opt/ti/ti-cgt-armllvm_5.1.0.LTS/bin/tiarmclang

# Paths
PROJ_DIR        := .
SYSCFG_DIR      := $(PROJ_DIR)/syscfg_gen
BUILD_DIR       := $(PROJ_DIR)/build

# Source files
STARTUP_SRC     := $(SDK_ROOT)/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c
STARTUP_OBJ     := $(BUILD_DIR)/startup_mspm0g350x_ticlang.o

OBJS            := $(BUILD_DIR)/laser_driver.o \
                   $(BUILD_DIR)/laser_pwm_control.o \
                   $(BUILD_DIR)/laser_sysctl.o \
                   $(BUILD_DIR)/laser_gpio.o \
                   $(BUILD_DIR)/ti_msp_dl_config.o \
                   $(STARTUP_OBJ)

# SysConfig
SYSCFG_FILE     := laser_driver.syscfg
SYSCFG_STAMP    := $(SYSCFG_DIR)/.generated
SYSCFG_PRODUCT  := $(SDK_ROOT)/.metadata/product.json

# Compiler flags
CPU_FLAGS       := -mcpu=cortex-m0plus -mthumb
OPT_FLAGS       := -O0 -g
INCLUDES        := \
    -I$(SYSCFG_DIR) \
    -I$(SDK_ROOT)/source \
    -I$(SDK_ROOT)/source/ti/devices/msp \
    -I$(SDK_ROOT)/source/ti/devices/msp/m0p \
    -I$(SDK_ROOT)/source/ti/devices/msp/m0p/peripheral_library \
    -I$(SDK_ROOT)/source/third_party/CMSIS/Core/Include

CFLAGS          := $(CPU_FLAGS) $(OPT_FLAGS) $(INCLUDES) \
                   @$(SYSCFG_DIR)/device.opt

# Linker flags
DRIVERLIB       := $(SDK_ROOT)/source/ti/driverlib/lib/ticlang/m0p/mspm0g1x0x_g3x0x/driverlib.a
LINKER_CMD      := $(SDK_ROOT)/source/ti/devices/msp/m0p/linker_files/ticlang/mspm0g3507.cmd
LFLAGS          := -Wl,--rom_model \
                   -Wl,-m,$(BUILD_DIR)/laser_driver.map \
                   -T$(LINKER_CMD) \
                   -Wl,--search_path=$(SDK_ROOT)/source \
                   $(SYSCFG_DIR)/device.cmd.genlibs \
                   $(SYSCFG_DIR)/device_linker.cmd

# Output
TARGET          := $(BUILD_DIR)/laser_driver.out

# ============================================================

.PHONY: all clean

all: $(TARGET)
	@echo "Build complete: $(TARGET)"

# Link
$(TARGET): $(OBJS) | $(BUILD_DIR)
	$(CC) $(CPU_FLAGS) $(OBJS) $(LFLAGS) -o $@

# Compile app source
$(BUILD_DIR)/laser_driver.o: $(PROJ_DIR)/laser_driver.c $(SYSCFG_STAMP) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/laser_pwm_control.o: $(PROJ_DIR)/laser_pwm_control.c $(SYSCFG_STAMP) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/laser_sysctl.o: $(PROJ_DIR)/laser_sysctl.c $(SYSCFG_STAMP) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/laser_gpio.o: $(PROJ_DIR)/laser_gpio.c $(SYSCFG_STAMP) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# Compile SysConfig generated source
$(BUILD_DIR)/ti_msp_dl_config.o: $(SYSCFG_DIR)/ti_msp_dl_config.c $(SYSCFG_STAMP) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# Compile startup file
$(STARTUP_OBJ): $(STARTUP_SRC) $(SYSCFG_STAMP) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# SysConfig code generation
$(SYSCFG_STAMP): $(SYSCFG_FILE) | $(SYSCFG_DIR)
	@echo "Running SysConfig..."
	$(SYSCONFIG_ROOT)/sysconfig_cli.sh \
		--script $(SYSCFG_FILE) \
		--product $(SYSCFG_PRODUCT) \
		--compiler ticlang \
		--output $(SYSCFG_DIR)
	@touch $(SYSCFG_STAMP)

# Create output directories
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(SYSCFG_DIR):
	mkdir -p $(SYSCFG_DIR)

# Clean everything that isn't committed
clean:
	rm -rf $(BUILD_DIR) $(SYSCFG_DIR)

