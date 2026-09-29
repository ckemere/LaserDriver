# =========================================================================== 3. set-point
sh.box(8 * u, 60 * u, 95 * u, 104 * u, "3. SET-POINT  (TL431 -> /2.5 -> MCP4921 VREF = 1.0 V -> VSET_P; U5B inverts -> VSET_N; 74HC4053 -> V_IN)")
put("R7", 14, 70)
put("U3", 14, 75.5)
PWR("R7.1")
W("R7.2", "U3.2")
W("U3.1", pt(12, 72.5), pt(14, 72.5))
PWR("U3.3")
put("R8", 21.5, 70, rot=90)
put("R9", 24, 71.5)
put("C9", 27, 71.5)
W("R7.2", pt(17, 71.5), pt(17, 70), "R8.1")      # VREF_2V5
PWR("R9.2"); PWR("C9.2")
put("U4", 38, 72)
W("R8.2", "U4.6")                                # VREF_DAC = 1.0 V (passes R6.1, C13.1)
sh.wired |= {("R9", "1"), ("C9", "1")}
for pin in ("2", "3", "4"):
    LBL(f"U4.{pin}", length=2.54)
W("U4.5", pt(33, 74), pt(33, 75))
PWR(None, "GND_ISO", at=pt(33, 75), up=(0, 1))
PWR("U4.1"); PWR("U4.7")
W("U4.8", pt(59, 72))                            # VSET_P
# inverter U5B
put("U5", 67, 80, unit=2)
put("R10", 60.5, 81, rot=90)
put("R11", 67, 85.5, rot=90)
W(pt(59, 72), pt(59, 81), "R10.1")
W("R10.2", "U5.6")
W(pt(63, 81), pt(63, 85.5), "R11.1")
W("R11.2", pt(71, 85.5), pt(71, 80))
W("U5.7", pt(73, 80), pt(73, 81), pt(79, 81))    # VSET_N -> 1Y1
W("U5.5", pt(63, 79), pt(63, 77.5))
PWR(None, "GND_ISO", at=pt(63, 77.5), up=(0, -1))
# 74HC4053
put("U6", 84, 84, ref_at=(-7.62, -16.51), val_at=(7.62, -16.51))
W(pt(59, 72), pt(76, 72), pt(76, 80), "U6.12")   # VSET_P -> 1Y0
sh.wired.add(("U6", "13"))
W("U6.2", pt(78, 83)); W("U6.5", pt(78, 86)); W("U6.3", pt(78, 87))
W(pt(78, 83), pt(78, 88))
PWR(None, "GND_ISO", at=pt(78, 88), up=(0, 1))
sh.NET("U6.14", "SW_P", length=2.54)
sh.NET("U6.1", "SW_P", length=2.54 * 3)
LBL("U6.15", length=2.54)                        # V_IN -> output stage
PWR("U6.4")
PWR("U6.16")
W("U6.9", pt(83, 91.5)); W("U6.6", pt(84, 91.5)); W("U6.8", pt(86, 91.5)); W(pt(83, 91.5), pt(86, 91.5))
W(pt(85, 91.5), pt(85, 92.5))
PWR(None, "GND_ISO", at=pt(85, 92.5), up=(0, 1))
W("U6.7", pt(87, 91), pt(90, 91), pt(90, 92.5))
PWR(None, "-5V_ISO", at=pt(90, 92.5), up=(0, 1))
W("U6.11", pt(81, 94), pt(69, 94))
LBL(None, "CATH", at=pt(69, 94), direction=(-1, 0))
W("U6.10", pt(82, 96), pt(69, 96))
LBL(None, "EN", at=pt(69, 96), direction=(-1, 0))
# decoupling row
for i, c in enumerate(("C10", "C13")):
    put(c, 14 + 5 * i, 90)
    PWR(f"{c}.1"); PWR(f"{c}.2")
put("C14", 24, 90, rot=180)
PWR("C14.1"); PWR("C14.2")
sh.text("Decoupling at: C10 U4, C13/C14 U6.  MCP4921: set BUF = 1 (VREF input buffered), gain 1x.", 10 * u, 97 * u)
sh.text("VSET_P = 0..1 V.  4053: S1 = CATH picks -VSET / +VSET, S2 = EN picks that or 0 V -> V_IN.  EN low (isolator fail-safe) = zero current.",
        10 * u, 101 * u)
sh.text("Firmware: set CATH before raising EN, hold it until EN falls.  Switch 3 unused (tied to GND).", 10 * u, 103 * u)

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
sh.text("R_SENSE = R14 = 2.00 k 0.1 %: I = V_IN / 2 k, 500 uA full scale (0.12 uA/LSB).", 99 * u, 97 * u)
sh.text("C16: 1 uF DC block. Cable: twisted pair, shield to E2, < 500 pF E1-to-GND.", 99 * u, 99 * u)

# =========================================================================== 5. SHORT switch
sh.box(98 * u, 102 * u, 137 * u, 126 * u, "5. SHORT  (DG419 across E1-E2)")
put("U7", 118, 113, ref_at=(0, -8.89), val_at=(0, 8.89))
LBL("U7.1", length=2.54)
LBL("U7.2", length=2.54)
sh.NC("U7.8")
NET("U7.6", "HOLD", length=2.54)
PWR("U7.4"); PWR("U7.5"); PWR("U7.3"); PWR("U7.7")
sh.text("HOLD low (no EN/CATH for ~200 us): S1-D closed, E1 shorted to E2.", 99 * u, 123 * u)
sh.text("HOLD high: open (tOFF ~60 ns). 20 ohm on, 60 pC injection, reset every cycle.", 99 * u, 125 * u)

# =========================================================================== 6. fault detector
sh.box(140 * u, 60 * u, 196 * u, 104 * u, "6. FAULT DETECTOR  (LM393 window on E1 -> FAULT_n; low also = isolated side unpowered)")
put("R20", 146.5, 70, rot=90)
put("R22", 150, 68.5)
put("R21", 150, 71.5)
put("C18", 153, 71.5)
LBL("R20.1", length=2.54)
PWR("R22.1"); PWR("R21.2"); PWR("C18.2")
W("R20.2", pt(155, 70))                           # E1_LS
sh.wired |= {("R22", "2"), ("R21", "1"), ("C18", "1")}
put("R23", 146.5, 83, rot=90)
put("R25", 150, 81.5)
put("R24", 150, 84.5)
PWR("R23.1"); PWR("R25.1"); PWR("R24.2")
W("R23.2", pt(157, 83), pt(157, 78), pt(159, 78)) # TH_P
sh.wired |= {("R25", "2"), ("R24", "1")}
put("R26", 146.5, 96, rot=270)
put("R28", 150, 94.5)
put("R27", 150, 97.5)
PWR("R26.2"); PWR("R28.1"); PWR("R27.2")
W("R26.1", pt(158, 96), pt(158, 93), pt(159, 93)) # TH_N
sh.wired |= {("R28", "2"), ("R27", "1")}
put("U8", 162, 79, unit=1)
put("U8", 162, 92, unit=2)
sh.wired |= {("U8", "3"), ("U8", "6")}
W(pt(155, 70), pt(155, 91), pt(159, 91))          # E1_LS to both comparators
W(pt(155, 80), "U8.2")
sh.wired.add(("U8", "5"))
W("U8.1", pt(168, 79), pt(168, 92))
W("U8.7", pt(168, 92))
put("R19", 171, 83.5)
PWR("R19.1")
W(pt(168, 85), pt(176, 85))                       # FAULT_n (open collectors, R19 pull-up) -> U1 INF
sh.wired.add(("R19", "2"))
LBL(None, "FAULT_n", at=pt(176, 85), direction=(1, 0))
put("U8", 172, 68, unit=3); put("C19", 176, 68)
for s_ in ("U8.8", "U8.4", "C19.1", "C19.2"):
    PWR(s_)
sh.text("E1_LS = 0.0767*E1 + 1.42 V; TH_P/TH_N track the rails: trips at |E1| > 0.915*V (13.9 V at +/-15 V).", 141 * u, 99 * u)
sh.text("FAULT_n low while E1 is past the trip point (a few us before U5A saturates; open electrode: within ~5 us of EN)", 141 * u, 101 * u)
sh.text("and while +5V_ISO is down (R19 unpowered).  The HAT latches it on TIMA0_FAULT0 and forces EN/CATH low.", 141 * u, 103 * u)
