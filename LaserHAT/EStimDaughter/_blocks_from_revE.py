# =========================================================================== 3. set-point
sh.box(8 * u, 60 * u, 95 * u, 104 * u, "3. SET-POINT  (DAC60501 I2C, internal 2.5 V ref / 2 -> 0..1.25 V = VSET_P; U5B inverts -> VSET_N; ADG1436 -> V_IN)")
put("U4", 38, 72)
W("U4.6", pt(31, 70), pt(31, 66)); LBL(None, "SCL", at=pt(31, 66), direction=(0, -1))
W("U4.8", pt(32.5, 71), pt(32.5, 66)); LBL(None, "SDA", at=pt(32.5, 66), direction=(0, -1))
W("U4.5", pt(29, 72), pt(29, 64), pt(38, 64), pt(38, 66.5))   # SPI2C high = I2C mode, tied to the VDD stub end
PWR("U4.1")                                                   # +5V_ISO at (38, 66)
W("U4.7", pt(31, 73), pt(31, 77)); PWR(None, "GND_ISO", at=pt(31, 77), up=(0, 1))   # A0 = AGND -> address 0x48
PWR("U4.4")
W("U4.2", pt(59, 72))                            # VSET_P
put("C9", 46, 76)
W("U4.10", pt(46, 73), "C9.1")                   # VREFIO (2.5 V reference out) decoupled by C9
PWR("C9.2")
# isolated-side I2C pull-ups
put("R9", 24, 69); PWR("R9.1"); LBL("R9.2", length=2.54)
put("R15", 28, 69); PWR("R15.1"); LBL("R15.2", length=2.54)
# inverter U5B
put("U5", 67, 80, unit=2)
put("R10", 60.5, 81, rot=90)
put("R11", 67, 85.5, rot=90)
W(pt(59, 72), pt(59, 81), "R10.1")
W("R10.2", "U5.6")
W(pt(63, 81), pt(63, 85.5), "R11.1")
W("R11.2", pt(71, 85.5), pt(71, 80))
W("U5.5", pt(63, 79), pt(63, 77.5))
PWR(None, "GND_ISO", at=pt(63, 77.5), up=(0, -1))
# ADG1436 dual SPDT (mirrored: S / D pins face west, IN1 / EN / IN2 east).  Switch 2 = phase (CATH), switch 1 = gate (EN)
put("U6", 84, 84, mirror=True, ref_at=(0, -13.97), val_at=(0, 13.97))
W(pt(59, 72), pt(76, 72), pt(76, 84.5), "U6.10")  # VSET_P -> S2B (on while CATH low)
W("U5.7", pt(73, 80), pt(73, 86.5), "U6.8")       # VSET_N -> S2A (on while CATH high)
sh.LAB("VSET_P", pt(62, 72))                     # net labels on the two set-point wires
sh.LAB("VSET_N", pt(75, 86.5))
sh.NET("U6.9", "SW_P", length=2.54)               # D2
sh.NET("U6.16", "SW_P", length=2.54)              # S1A (on while EN high)
PWR("U6.2", length=2.54)                          # S1B = 0 V (EN low)
LBL("U6.1", length=2.54)                          # D1 = V_IN -> output stage
LBL("U6.6", length=2.54)                          # CATH
LBL("U6.15", length=2.54)                         # EN
PWR("U6.12")                                      # EN pin high (VDD = +V_STIM)
PWR("U6.11"); PWR("U6.3"); PWR("U6.4")            # VDD / VSS / GND
W("U6.17", pt(85, 89)); W("U6.3", pt(86, 89)); W(pt(85, 89), pt(86, 89))    # exposed pad to VSS
for p_ in ("5", "7", "13", "14"):
    sh.NC(f"U6.{p_}")
# decoupling row
for i, c in enumerate(("C10", "C13")):
    put(c, 14 + 5 * i, 90)
    PWR(f"{c}.1"); PWR(f"{c}.2")
put("C14", 24, 90, rot=180)
PWR("C14.1"); PWR("C14.2")
sh.text("Decoupling at: C10 U4 VDD, C9 U4 VREFIO, C13/C14 (+/-V) on the west feed near U6.  DAC60501Z: I2C address 0x48; write GAIN (0x04) = 0x0100 first, then DAC (0x08) = code << 4.", 10 * u, 97 * u)
sh.text("VSET_P = 0..1.25 V.  U6 sw 2: CATH picks VSET_P (0) / VSET_N (1) -> SW_P; sw 1: EN picks 0 V (0) / SW_P (1) -> V_IN.  EN low (isolator fail-safe) = zero current.",
        10 * u, 101 * u)
sh.text("Firmware: set CATH before raising EN, hold it until EN falls.  ADG1436 EN pin tied high: EN low would float V_IN.", 10 * u, 103 * u)

# =========================================================================== 4. output stage
sh.box(98 * u, 60 * u, 137 * u, 100 * u, "4. OUTPUT STAGE  (floating-load V->I, I = V_IN / R_SENSE)")
put("U5", 112, 80, unit=1)
put("R12", 104.5, 79, rot=90)
put("C15", 107, 80.5)
LBL("R12.1", length=2.54)
W("R12.2", "U5.3")
sh.wired.add(("C15", "1"))
PWR("C15.2")
put("R13", 118.5, 80, rot=90)
put("C16", 124.5, 80, rot=90)
put("J1", 132.5, 80.5, val_at=(0, 5.08))
W("U5.1", "R13.1")
W("R13.2", "C16.1")                               # E1
W("C16.2", "J1.1")
W(pt(122, 80), pt(122, 83))
LBL(None, "E1", at=pt(122, 83), direction=(0, 1))
put("R14", 116, 89.5)
put("TP1", 112, 88)
W("U5.2", pt(108, 81), pt(108, 88), pt(129, 88), pt(129, 81), "J1.2")   # ISENSE
sh.wired |= {("R14", "1"), ("TP1", "1")}
W(pt(110, 88), pt(110, 91))
LBL(None, "ISENSE", at=pt(110, 91), direction=(0, 1))
PWR("R14.2")
put("U5", 104, 68, unit=3)
PWR("U5.8"); PWR("U5.4")
put("C11", 108, 68)
put("C12", 112, 68, rot=180)
PWR("C11.1"); PWR("C11.2"); PWR("C12.1"); PWR("C12.2")
sh.text("R_SENSE = R14 = 2.49 k 0.1 %: I = V_IN / 2.49 k, 502 uA full scale (0.123 uA/LSB).", 99 * u, 97 * u)
sh.text("C16: 1 uF DC block. Cable: twisted pair, shield to E2, < 500 pF E1-to-GND.", 99 * u, 99 * u)

# =========================================================================== 5. SHORT switch
sh.box(98 * u, 102 * u, 137 * u, 126 * u, "5. SHORT  (DG419B across E1-E2, driven by RELEASE from the HAT)")
put("U7", 118, 113, ref_at=(0, -8.89), val_at=(0, 8.89))
LBL("U7.1", length=2.54)
LBL("U7.2", length=2.54)
sh.NC("U7.8")
LBL("U7.6", length=2.54)
PWR("U7.4"); PWR("U7.5"); PWR("U7.3"); PWR("U7.7")
sh.text("RELEASE low (idle, HAT unpowered or faulted): S1-D closed, E1 shorted to E2.", 99 * u, 123 * u)
sh.text("RELEASE high: open (tOFF ~50 ns). 15 ohm on, 38 pC injection.  Firmware: RELEASE >= 1 us before EN.", 99 * u, 125 * u)

# =========================================================================== 6. fault detector
sh.box(140 * u, 60 * u, 196 * u, 104 * u, "6. FAULT DETECTOR  (TLV1702 window on E1 -> FAULT_n; low also = isolated side unpowered)")
# threshold string between the rails: TH_P / TH_N
put("R23", 148, 70, rot=0); put("R24", 148, 79, rot=0); put("R25", 148, 88, rot=0)
PWR("R23.1", length=2.54)                                # +V_STIM
W("R23.2", "R24.1"); W("R24.2", "R25.1")
PWR("R25.2", length=2.54)                                # -V_STIM
W(pt(148, 74.5), pt(153, 74.5)); sh.wired.add(("R24", "1"))      # TH_P tap
W(pt(148, 83.5), pt(153, 83.5)); sh.wired.add(("R25", "1"))      # TH_N tap
# comparators
# units swapped 2026-09-29 for the layout: B is the upper (TH_P) comparator, A the lower (TH_N) one
put("U8", 162, 76, unit=2)          # B: +IN = TH_P (pin 5, y 75), -IN = E1 (pin 6, y 77): low when E1 > TH_P
put("U8", 162, 89, unit=1)          # A: +IN = E1 (pin 3, y 88), -IN = TH_N (pin 2, y 90): low when E1 < TH_N
W(pt(153, 74.5), pt(153, 75), "U8.5")                    # TH_P -> B+
W(pt(153, 83.5), pt(153, 90), "U8.2")                    # TH_N -> A-
W("U8.6", pt(156, 77), pt(156, 68), pt(144, 68))         # E1 -> B-  (the vertical crosses the TH_P feed: no junction)
W("U8.3", pt(157, 88), pt(157, 77))                      # E1 -> A+  (joins the B- run at (157, 77))
LBL(None, "E1", at=pt(144, 68), direction=(-1, 0))
W("U8.7", pt(168, 76), pt(168, 89)); W("U8.1", pt(168, 89))     # wired-OR (FAULT_OC)
sh.LAB("FAULT_OC", pt(168, 80))
# level shift to the isolator: R26 series, D2 clamp to GND_ISO, R19 pull-up
put("R26", 172, 82, rot=90)
W(pt(168, 82), "R26.1")
put("R19", 179, 78.5); PWR("R19.1")
put("D2", 179, 86, rot=270, ref_at=(2.54, -1.27), val_at=(2.54, 1.27))  # K up (FAULT_n), A down (GND_ISO)
W("R26.2", pt(179, 82)); W("R19.2", pt(179, 82)); W("D2.1", pt(179, 82))
W(pt(179, 82), pt(186, 82))
LBL(None, "FAULT_n", at=pt(186, 82), direction=(1, 0))
PWR("D2.2")
put("U8", 172, 68, unit=3); put("C19", 176, 68)
for s_ in ("U8.8", "U8.4", "C19.1", "C19.2"):
    PWR(s_)
sh.text("U8 runs from +/-V and compares E1 with taps 0.043 x (V+ + |V-|) inside each rail: |E1| > 0.915 V for equal packs (13.9 V at +/-15 V).", 141 * u, 97 * u)
sh.text("FAULT_n low while E1 is past the trip point (a few us before U5A saturates; open electrode: within ~5 us of EN), while", 141 * u, 99 * u)
sh.text("+5V_ISO is down (R19 unpowered) and when one pack is missing.  R26 / D2 shift the -V-referenced open collectors to 0..5 V.", 141 * u, 101 * u)
sh.text("The HAT latches it on TIMA0_FAULT0 and forces EN/CATH low.", 141 * u, 103 * u)
