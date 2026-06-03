# ============================================================
# Laser Driver - top-level dispatcher
# ============================================================
# Picks a toolchain Makefile based on `uname`:
#
#   ARM Linux  (Raspberry Pi)   -> Makefile.gcc      (arm-none-eabi-gcc)
#   x86_64 Linux                -> Makefile.ticlang  (TI ARM CLANG)
#   macOS  (Intel or Apple Si)  -> Makefile.ticlang  (TI ARM CLANG)
#
# All targets (`all`, `clean`, etc.) and command-line overrides
# (`CC=...`, `TI_TOOLCHAIN_VER=...`) are forwarded to the chosen
# sub-Makefile.  To force a toolchain explicitly:
#
#   make -f Makefile.gcc      # GCC build (any host)
#   make -f Makefile.ticlang  # TI CLANG build (any host)

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# ARM Linux = Raspberry Pi (or any ARM-class Linux host).  TI ARM
# CLANG isn't available for ARM hosts, so fall back to GCC.
ifeq ($(UNAME_S),Linux)
  ifneq (,$(filter $(UNAME_M),aarch64 armv7l armv6l))
    SUB := Makefile.gcc
  endif
endif
SUB ?= Makefile.ticlang

# Forward every goal (and the implicit default goal) to the chosen
# Makefile.  --no-print-directory keeps the output clean.
.DEFAULT_GOAL := all
all:
	@$(MAKE) --no-print-directory -f $(SUB) all

%:
	@$(MAKE) --no-print-directory -f $(SUB) $@

.PHONY: all
