# laserhat-brokerd — build natively on the Pi (or on a dev box for testing).
#
#   make            -> ./laserhat-brokerd
#   make clean

CC      ?= cc
CFLAGS  ?= -O2 -g
CFLAGS  += -std=c11 -Wall -Wextra -Werror -pthread -I../../Firmware
LDFLAGS += -pthread
LDLIBS  += -lm

ifeq ($(shell uname),Darwin)
CFLAGS  += -D_DARWIN_C_SOURCE
else
CFLAGS  += -D_GNU_SOURCE
endif

SRCS = main.c mcu.c ipc.c json.c gpio.c trigger.c
OBJS = $(SRCS:.c=.o)
HDRS = brokerd.h udp_trigger.h ../../Firmware/protocol.h

laserhat-brokerd: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS) $(LDLIBS)

%.o: %.c $(HDRS)
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) laserhat-brokerd

.PHONY: clean
