"""
LaserDriverHAT (2026-10-30): the LaserHAT Rev 2 core of the StimHAT and the LaserDaughter module's laser-diode driver on
one Raspberry Pi HAT.  Single source of truth for symbol, value, footprint, LCSC code and pin -> net; tools/netcheck.py
proves the drawn schematic matches it.

Core: the StimHAT's (refs as on the Rev 2 HAT, see ../StimHAT/README.md), unchanged except
  * U7's east column (pins 26-31, the e-stim lines on the StimHAT) carries the laser lines:
      PA22 DB_PWM_A (TIMA0_C1: the firmware's CCP1 = laser switch)   PA23 DB_PWM_B (TIMA0_C3: CCP3 = dummy switch)
      PA26 DB_ADC_A (ADC0 ch 1, photodiode)   PA27 DB_ADC_B (ADC0 ch 0, LASER_V x 33k / 133k compliance divider)
  * DB_DAC (the laser current set-point) needs DAC0_OUT, which only PA15 (pin 19) has: BUTTON3 (joystick down) moved
    from PA15 to PA6 (pin 10); PA3, PA24 and PA25 are spare (the laser driver has no fault output: J8.3 was unconnected
    on the module)
  * J7 is "SYNC OUT" (PA17 mirrors the laser pulse envelope through U8B, as before)
Laser driver: every part of ../LaserDaughter (rev 2.0, 2026-10-01) with its values, footprints and LCSC codes
(../tools/lcsc_parts.py LASER) and the module's own connections; refs kept where the HAT core leaves them free
(D1-D4, J2, J4, L1, Q1, Q2, Rs1, SW5), +200 otherwise (R1-R6 / R11 / R12 -> R201-R206 / R211 / R212, C8 / C9 / C11 / C12
-> C208 / C209 / C211 / C212, U2 / U3 -> U202 / U203, J5 -> J205).  The module's header sockets J1 (HAT_J8) and J3
(HAT_J9) are gone: their lines are nets to U7 and the HAT's +5V / GND.  Internal nets keep the module's names (local
labels: /SW /IREF /DUMMY_TOP /DUMMY_MID /DUMMY_BOT /LaserDrive /IDrive; +12V, LASER_V); the module's auto-named nets are
named LD_CATHODE, PD_ANODE, PD_CATHODE, Q2_GATE and BOOST_FB.
"""

R0402, R0603 = "Resistor_SMD:R_0402_1005Metric", "Resistor_SMD:R_0603_1608Metric"
C0402, C0603, C0805, C1206 = ("Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric",
                              "Capacitor_SMD:C_0805_2012Metric", "Capacitor_SMD:C_1206_3216Metric")
SOT23, SOT236, SOT89, SOT363 = ("Package_TO_SOT_SMD:SOT-23", "Package_TO_SOT_SMD:SOT-23-6", "Package_TO_SOT_SMD:SOT-89-3",
                                "Package_TO_SOT_SMD:SOT-363_SC-70-6")
SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
SOD123, SOD323, LED0603 = "Diode_SMD:D_SOD-123", "Diode_SMD:D_SOD-323", "Diode_SMD:D_0603_1608Metric"
SOIC8, SSOP16, TSSOP8, TSSOP16, VSSOP8, VSSOP10 = ("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Package_SO:SSOP-16_3.9x4.9mm_P0.635mm",
                                                    "Package_SO:TSSOP-8_4.4x3mm_P0.65mm", "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",
                                                    "Package_SO:VSSOP-8_3x3mm_P0.65mm", "Package_SO:VSSOP-10_3x3mm_P0.5mm")
JEITA8 = "Package_SO:JEITA_SOIC-8_3.9x4.9mm_P1.27mm"
HDR2V = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
SOCK4V = "Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical"
TP = "TestPoint:TestPoint_Pad_D1.0mm"
HOLE = "MountingHole:MountingHole_2.7mm_M2.5"
JUMPER_R = "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"
JUMPER_T = "Jumper:SolderJumper-2_P1.3mm_Open_TrianglePad1.0x1.5mm"

# LCSC codes (0402 resistors and 0402 / 0603 capacitors are JLC basic parts)
L = dict(R100k="C25741", R10k="C25744", R1k="C11702", R4k7="C25900", R47k="C25792", R5k1="C25905", R2k="C4109",
         R3k9="C51721", R33="C25105", R100k01="C852472",
         C100n="C307331", C1u="C52923", C10n="C15195", C470n="C47339", C10u="C15850", LEDW="C2290", LEDR="C2286",
         USBC="C2988369", JOY="C202415", TS1088="C720477", MSK="C431540", EEPROM="C283445", LDO="C632000",
         LOADSW="C110466", CH340="C2977777", MCU="C22406180", BUF="C50714", PFET="C471913", DUALPNP="C154733")
# the laser module's codes, as in ../tools/lcsc_parts.py LASER (keyed by the module's refs)
LL = dict(C11="C15195", C12="C307331", C8="C12891", C9="C12891", D1="C37049", D3="C37049", D2="C209583", D4="C209582",
          L1="C503307", Q1="C428343", Q2="C274612", R1="C25741", R2="C25779", R3="C25783", R4="C25744", R6="C25744",
          R5="C25761", R11="C852624", R12="C25900", Rs1="C2105197", SW5="C221841", U2="C84817", U3="C55940")


def R(ref, val, a, b, fp=R0402, lcsc=""):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, fp=C0402, lcsc=""):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


PARTS = [
    # ================================================================ 1. Raspberry Pi header, USB-C, 5 V / 3.3 V
    # Samtec HLE SMD socket with pass-through holes (hand-fitted, as on the HAT): the Pi's header pins can reach a bonnet above
    dict(ref="J1", sym="GPIO_2x20", value="GPIO", fp="Footprints:Samtec_HLE-120-02-xxx-DV-BE-LC_2x20_P2.54mm_Horizontal", lcsc="",
         nets={"1": "+3V3_PI", "2": "+5V", "3": "I2C_SDA", "4": "+5V", "5": "I2C_SCL", "6": "GND", "7": None, "8": "PI_TXD",
               "9": "GND", "10": "PI_RXD", "11": None, "12": "PI_TRIGGER", "13": None, "14": "GND", "15": None, "16": None,
               "17": "+3V3_PI", "18": "SWCLK", "19": "MCU_PWR_EN", "20": "GND", "21": "NRST", "22": "SWDIO", "23": None, "24": None,
               "25": "GND", "26": None, "27": "ID_SDA", "28": "ID_SCL", "29": None, "30": "GND", "31": None, "32": None,
               "33": None, "34": "GND", "35": None, "36": None, "37": None, "38": None, "39": "GND", "40": None}),
    dict(ref="J5", sym="USB_C_16P", value="GT-USB-7010ASV", fp="Connector_USB:USB_C_Receptacle_G-Switch_GT-USB-7010ASV", lcsc=L["USBC"],
         nets={"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "S1": "GND", "A4": "VBUS", "B4": "VBUS", "A9": "VBUS", "B9": "VBUS",
               "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "A8": None, "B8": None}),
    R("R8", "5.1k", "CC1", "GND", lcsc=L["R5k1"]),
    R("R10", "5.1k", "CC2", "GND", lcsc=L["R5k1"]),
    # USB power switch (Q5, enabled by SW10) and ideal diode (Q3 / Q4) into +5V, which the Pi header also feeds
    dict(ref="Q5", sym="Q_PMOS_GSD", value="AP30P30Q", fp="Footprints:PDFN3333-8_PMOS_GSD", lcsc=L["PFET"],
         nets={"1": "PWR_EN", "2": "VBUS", "3": "VBUS_SW"}),
    R("R26", "100k", "VBUS", "PWR_EN", lcsc=L["R100k"]),
    dict(ref="SW10", sym="SW_SPDT", value="MSK12C02", fp="Footprints:SW_SPDT_Shouhan_MSK12C02", lcsc=L["MSK"],
         nets={"1": "GND", "2": "PWR_EN", "3": None}),
    dict(ref="Q3", sym="Q_PMOS_GSD", value="AP30P30Q", fp="Footprints:PDFN3333-8_PMOS_GSD", lcsc=L["PFET"],
         nets={"1": "IDEAL_G", "2": "+5V", "3": "VBUS_SW"}),
    dict(ref="Q4", sym="DMMT5401", value="DMMT5401", fp=SOT236, lcsc=L["DUALPNP"],
         nets={"1": "IDEAL_B", "2": "IDEAL_B", "3": "IDEAL_B", "4": "IDEAL_G", "5": "+5V", "6": "VBUS_SW"}),
    R("R21", "47k", "IDEAL_B", "GND", lcsc=L["R47k"]),
    R("R22", "10k", "IDEAL_G", "GND", lcsc=L["R10k"]),
    dict(ref="D5", sym="LED", value="KT-0603W", fp=LED0603, lcsc=L["LEDW"], nets={"1": "D5_K", "2": "+5V"}),
    R("R13", "2k", "D5_K", "GND", lcsc=L["R2k"]),
    C("C12", "1uF", "+5V", "GND", lcsc=L["C1u"]),             # MCP1700 input: >= 1 uF per its datasheet (audit 2026-10-30)
    dict(ref="U4", sym="MCP1700", value="MCP1700T-3302E/MB", fp=SOT89, lcsc=L["LDO"], nets={"1": "GND", "2": "+5V", "3": "+3V3"}),
    C("C6", "100nF", "+3V3", "GND", lcsc=L["C100n"]),
    C("C13", "1uF", "+3V3", "GND", lcsc=L["C1u"]),
    dict(ref="U5", sym="AP2171W", value="AP2171W", fp=SOT235, lcsc=L["LOADSW"],
         nets={"1": "MSPM0_3V3", "2": "GND", "3": None, "4": "MCU_PWR_EN", "5": "+3V3"}),
    R("R7", "10k", "+3V3", "MCU_PWR_EN", lcsc=L["R10k"]),
    C("C1", "100nF", "MSPM0_3V3", "GND", lcsc=L["C100n"]),
    C("C2", "10uF", "MSPM0_3V3", "GND", fp=C0805, lcsc=L["C10u"]),
    C("C16", "100nF", "MSPM0_3V3", "GND", lcsc=L["C100n"]),
    dict(ref="JP5", sym="Jumper2", value="STANDALONE_3V3", fp=JUMPER_R, lcsc="", nets={"1": "+3V3", "2": "+3V3_PI"}),
    C("C15", "100nF", "+3V3_PI", "GND", lcsc=L["C100n"]),
    C("C18", "100nF", "+3V3_PI", "GND", lcsc=L["C100n"]),
    R("R19", "4.7k", "+3V3_PI", "I2C_SDA", lcsc=L["R4k7"]) | {"dnp": True},
    R("R20", "4.7k", "+3V3_PI", "I2C_SCL", lcsc=L["R4k7"]) | {"dnp": True},
    # HAT ID EEPROM
    dict(ref="U1", sym="M24C32", value="M24C32-WDW6TP", fp=TSSOP8, lcsc=L["EEPROM"],
         nets={"1": None, "2": None, "3": None, "4": "GND", "5": "ID_SDA", "6": "ID_SCL", "7": "JP1_A", "8": "+3V3_PI"}),
    dict(ref="JP1", sym="Jumper2", value="ID_WP", fp=JUMPER_R, lcsc="", nets={"1": "JP1_A", "2": "+3V3_PI"}),
    R("R1", "3.9k", "+3V3_PI", "ID_SDA", lcsc=L["R3k9"]),
    R("R2", "3.9k", "+3V3_PI", "ID_SCL", lcsc=L["R3k9"]),
    # ================================================================ 2. MCU, USB-UART, reset, BSL, buttons, LEDs, display socket
    dict(ref="U7", sym="MSPM0G3507", value="MSPM0G1507SRHBR", fp="laserdriverhat:VQFN32_RHB_TEX", lcsc=L["MCU"],
         # LaserDriverHAT (2026-10-30): the StimHAT's HAT-core pins unchanged; the e-stim east column (pins 26-31) carries the
         # laser lines: PA22 DB_PWM_A (TIMA0_C1 = the firmware's CCP1 laser switch), PA23 DB_PWM_B (TIMA0_C3 = CCP3 dummy
         # switch), PA26 / PA27 DB_ADC_A / DB_ADC_B (ADC0 ch 1 / ch 0); DB_DAC needs DAC0_OUT, which exists only on PA15
         # (pin 19), so BUTTON3 (joystick down) moved from PA15 to PA6 (pin 10); PA3 (7), PA24 (28), PA25 (29) spare
         nets={"1": "I2C_SDA", "2": "I2C_SCL", "3": "NRST", "4": "MSPM0_3V3", "5": "GND", "6": "ROSC",
               "7": None, "8": "PI_TRIGGER", "9": "LED_MCU", "10": "BUTTON3", "11": "BUTTON4", "12": "PI_RXD", "13": "PI_TXD",
               "14": "MCU_UART_TX", "15": "MCU_UART_RX", "16": "BUTTON1", "17": "BUTTON6", "18": "BUTTON2", "19": "DB_DAC",
               "20": "BUTTON5", "21": "MCU_STIM_OUT", "22": "BSL_INVOKE", "23": "SWDIO", "24": "SWCLK", "25": "MCU_STIM_IN",
               "26": "DB_PWM_A", "27": "DB_PWM_B", "28": None, "29": None, "30": "DB_ADC_A", "31": "DB_ADC_B", "32": "VCORE",
               "33": "GND"}),
    R("R4", "100k 0.1%", "ROSC", "GND", lcsc=L["R100k01"]),
    C("C4", "470nF", "VCORE", "GND", lcsc=L["C470n"]),
    R("R3", "4.7k", "MSPM0_3V3", "NRST", lcsc=L["R4k7"]),      # 4.7k: NRST ~3.0 V against the Pi's boot-time pull-down on GPIO9 (audit 2026-10-30)
    C("C3", "10nF", "NRST", "GND", lcsc=L["C10n"]),
    dict(ref="JP4", sym="Jumper2", value="RTS_NRST", fp=JUMPER_T, lcsc="", nets={"1": "NRST", "2": "CH340_RTS"}),
    dict(ref="U6", sym="CH340N", value="CH340N", fp=JEITA8, lcsc=L["CH340"],
         nets={"1": "USB_DP", "2": "USB_DM", "3": "GND", "4": "CH340_RTS", "5": "MSPM0_3V3", "6": "MCU_UART_RX", "7": "MCU_UART_TX", "8": "MSPM0_3V3"}),
    C("C17", "100nF", "MSPM0_3V3", "GND", lcsc=L["C100n"]),   # at U6 (U8 is bypassed by C16, 2.6 mm from its VCC pin on the same trace)
    dict(ref="SW6", sym="SW_Push", value="TS-1088-AR02016", fp="Button_Switch_SMD:SW_SPST_TS-1088-xR020", lcsc=L["TS1088"],
         nets={"1": "BSL_INVOKE", "2": "MSPM0_3V3"}),
    dict(ref="D7", sym="LED", value="KT-0603R", fp=LED0603, lcsc=L["LEDR"], nets={"1": "D7_K", "2": "LED_MCU"}),
    R("R15", "2k", "D7_K", "GND", lcsc=L["R2k"]),
    dict(ref="SW7", sym="Joystick5", value="SKRHADE010", fp="laserdriverhat:SW_ALPS_SKRHADE010", lcsc=L["JOY"],
         # mounted at 135 deg: contact A (pin 1) = push south = down, B (4) = west = left, C (3) = east = right, D (6) = north = up
         nets={"1": "BUTTON3", "2": "BUTTON2", "3": "BUTTON6", "4": "BUTTON1", "5": "GND", "6": "BUTTON4"}),
    dict(ref="SW9", sym="SW_Push", value="TS-1088-AR02016", fp="Button_Switch_SMD:SW_SPST_TS-1088-xR020", lcsc=L["TS1088"],
         nets={"1": "BUTTON5", "2": "GND"}),
    dict(ref="J10", sym="Conn_01x04", value="OLED 0.91 (GND VCC SCL SDA)", fp=SOCK4V, lcsc="", dnp=True,
         nets={"1": "GND", "2": "+3V3_PI", "3": "I2C_SCL", "4": "I2C_SDA"}),
    # ================================================================ 3. BNC trigger in / sync out (MCU_STIM_OUT mirrors the pulse envelope)
    dict(ref="J6", sym="BNC", value="BNC TRIGGER IN", fp="laserdriverhat:BNC_Amphenol_031-5540_RA", lcsc="",
         nets={"1": "BNC_IN", "2": "GND"}),
    dict(ref="J7", sym="BNC", value="BNC SYNC OUT", fp="laserdriverhat:BNC_Amphenol_031-5540_RA", lcsc="",
         nets={"1": "BNC_OUT", "2": "GND"}),
    R("R23", "1k", "BUF_IN", "BNC_IN", lcsc=L["R1k"]),
    R("R24", "100k", "BUF_IN", "GND", lcsc=L["R100k"]),
    dict(ref="U8", sym="74LVC2G17", value="SN74LVC2G17DCKR", fp=SOT363, lcsc=L["BUF"],
         nets={"1": "BUF_IN", "2": "GND", "3": "MCU_STIM_OUT", "4": "BUF_OUT", "5": "MSPM0_3V3", "6": "MCU_STIM_IN"}),
    R("R25", "33", "BNC_OUT", "BUF_OUT", lcsc=L["R33"]),
    dict(ref="D9", sym="LED", value="KT-0603R", fp=LED0603, lcsc=L["LEDR"], nets={"1": "STIM_LED_K", "2": "BUF_OUT"}),
    R("R18", "2k", "STIM_LED_K", "GND", lcsc=L["R2k"]),
    # ================================================================ 4. laser-diode driver (the LaserDaughter module, rev 2.0)
    # boost 5 V -> 12 V: U202 MT3608, L1, D1, C208 / C209, R205 / R206 (FB 0.6 V x (1 + 187k / 10k) = 11.8 V)
    C("C208", "22uF 16V", "+5V", "GND", fp=C1206, lcsc=LL["C8"]),
    dict(ref="L1", sym="L", value="10uH Isat>=1.5A (SRN4018-100M)", fp="Inductor_SMD:L_Bourns-SRN4018", lcsc=LL["L1"],
         nets={"1": "+5V", "2": "SW"}),
    dict(ref="U202", sym="MT3608", value="MT3608", fp=SOT236, lcsc=LL["U2"],
         nets={"1": "SW", "2": "GND", "3": "BOOST_FB", "4": "+5V", "5": "+5V", "6": None}),
    dict(ref="D1", sym="D", value="DSK14", fp="Diode_SMD:D_SOD-123F", lcsc=LL["D1"], nets={"1": "+12V", "2": "SW"}),
    C("C209", "22uF 16V", "+12V", "GND", fp=C1206, lcsc=LL["C9"]),
    R("R205", "187k", "+12V", "BOOST_FB", lcsc=LL["R5"]),
    R("R206", "10k", "BOOST_FB", "GND", lcsc=LL["R6"]),
    # LASER_V = 5 V or 12 V (SW5: 1 = +12V, 2 = common, 3 = +5V)
    dict(ref="SW5", sym="SW_SPDT", value="PCM12SMTR", fp="Button_Switch_SMD:SW_SPDT_PCM12", lcsc=LL["SW5"],
         nets={"1": "+12V", "2": "LASER_V", "3": "+5V"}),
    # laser diode / photodiode socket (2 x 2 header, hand-fitted); J4 ties the PD cathode to LASER_V when closed
    dict(ref="J2", sym="LaserDiode_2x2", value="Conn_02x02_Counter_Clockwise", fp="Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical",
         lcsc="", nets={"1": "LASER_V", "2": "LD_CATHODE", "3": "PD_CATHODE", "4": "PD_ANODE"}),
    dict(ref="J4", sym="Jumper2", value="PD_K-LASER_V (solder jumper)", fp=JUMPER_R, lcsc="", dnp=True,
         nets={"1": "PD_CATHODE", "2": "LASER_V"}),
    # Q1 AO9926B (cascode steering pair): laser switch S1 / G1 = DB_PWM_A / D1 = LD cathode, dummy switch S2 / G2 = DB_PWM_B / D2
    dict(ref="Q1", sym="AO9926B", value="AO9926B", fp=SOIC8, lcsc=LL["Q1"],
         nets={"1": "LaserDrive", "2": "DB_PWM_A", "3": "LaserDrive", "4": "DB_PWM_B", "5": "DUMMY_BOT", "6": "DUMMY_BOT",
               "7": "LD_CATHODE", "8": "LD_CATHODE"}),
    # dummy load: LASER_V -> D3 -> D2 (2.7 V, shorted by the RED shunt J205) -> D4 (2.4 V) -> Q1's dummy switch
    dict(ref="D3", sym="D", value="DSK14", fp="Diode_SMD:D_SOD-123F", lcsc=LL["D3"], nets={"1": "DUMMY_TOP", "2": "LASER_V"}),
    dict(ref="D2", sym="D_Zener", value="2.7V 1W (KDZVTR2.7B)", fp="Diode_SMD:D_SOD-123F", lcsc=LL["D2"],
         nets={"1": "DUMMY_TOP", "2": "DUMMY_MID"}),
    dict(ref="D4", sym="D_Zener", value="2.4V 1W (KDZVTR2.4B)", fp="Diode_SMD:D_SOD-123F", lcsc=LL["D4"],
         nets={"1": "DUMMY_MID", "2": "DUMMY_BOT"}),
    dict(ref="J205", sym="Conn_01x02", value="RED_SHUNT", fp="Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical", lcsc="",
         nets={"1": "DUMMY_TOP", "2": "DUMMY_MID"}),
    # current sink: Q2 NDT3055L + Rs1 2R, U203 TLV2371 servo; IREF = DB_DAC x 10k / 49k, filtered by C211 (~102 mA / V)
    dict(ref="Q2", sym="Q_NMOS_GDS", value="NDT3055L", fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2", lcsc=LL["Q2"],
         nets={"1": "Q2_GATE", "2": "LaserDrive", "3": "IDrive"}),
    R("Rs1", "2R 1% 0.5W (ESR18EZPF2R00)", "IDrive", "GND", fp="Resistor_SMD:R_1206_3216Metric", lcsc=LL["Rs1"]),
    dict(ref="U203", sym="TLV2371", value="TLV2371DBV", fp=SOT235, lcsc=LL["U3"],
         nets={"1": "Q2_GATE", "2": "GND", "3": "IREF", "4": "IDrive", "5": "+5V"}),
    C("C212", "100nF", "+5V", "GND", lcsc=LL["C12"]),
    R("R203", "39k", "DB_DAC", "IREF", lcsc=LL["R3"]),
    R("R204", "10k", "IREF", "GND", lcsc=LL["R4"]),
    C("C211", "10nF", "IREF", "GND", lcsc=LL["C11"]),
    # monitors: photodiode load R212 4.7k, R211 1k 0.1 % into DB_ADC_A; LASER_V x 33k / 133k (R201 100k / R202 33k) into DB_ADC_B
    R("R212", "4.7k", "PD_ANODE", "GND", lcsc=LL["R12"]),
    R("R211", "1k 0.1%", "DB_ADC_A", "PD_ANODE", lcsc=LL["R11"]),
    R("R201", "100k", "LASER_V", "DB_ADC_B", lcsc=LL["R1"]),
    R("R202", "33k", "DB_ADC_B", "GND", lcsc=LL["R2"]),
    # ================================================================ 8. mechanical
    dict(ref="MH1", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
    dict(ref="MH2", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
    dict(ref="MH3", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
    dict(ref="MH4", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
]

BY_REF = {p["ref"]: p for p in PARTS}
assert len(BY_REF) == len(PARTS), "duplicate reference"

# hand-fitted parts: populated by us, not by JLC (no LCSC code, out of the BOM and CPL); DNP parts are marked dnp=True above
HAND_FIT = {"J1", "J6", "J7", "J2", "J205"}
# the laser module's refs on this board (module ref -> HAT ref; the module's J1 / J3 header sockets are not fitted)
MODULE_REFS = {"C8": "C208", "C9": "C209", "C11": "C211", "C12": "C212", "R1": "R201", "R2": "R202", "R3": "R203", "R4": "R204",
               "R5": "R205", "R6": "R206", "R11": "R211", "R12": "R212", "U2": "U202", "U3": "U203", "J5": "J205",
               "D1": "D1", "D2": "D2", "D3": "D3", "D4": "D4", "J2": "J2", "J4": "J4", "L1": "L1", "Q1": "Q1", "Q2": "Q2",
               "Rs1": "Rs1", "SW5": "SW5"}
