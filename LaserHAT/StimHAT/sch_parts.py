"""
StimHAT (2026-10-29): the LaserHAT Rev 2 core and the e-stim module's isolated stimulator on one Raspberry Pi HAT.
Single source of truth for symbol, value, footprint, LCSC code and pin -> net; tools/netcheck.py proves the drawn
schematic matches it.

Core (refs as on the Rev 2 HAT, nets as in its netlist, see ../CLAUDE.md "Rev 2 MCU pin map"), with these changes:
  * no J8 / J9 module sockets: the six module lines go straight to the stimulator block
      PA6  FAULT_H (TIMA0_FAULT0-capable, used as a falling-edge IRQ)   PA7  EN_H      PA12 CATH_H
      PA15 RELEASE_H                                                     PA17 SDA_H     PA22 SCL_H   (bit-banged I2C, as today)
  * NRST comes from Pi GPIO16 (header pin 36) instead of GPIO23 (pin 16): the Adafruit 4567 bonnet's joystick-right
    grounds GPIO23, which would reset the MCU.  GPIO23 is left unconnected.  (Pi side: LASERHAT_RESET_PIN = 16.)
  * SW7 is a five-way joystick (ALPS SKRHADE010) instead of the thumbwheel + the BACK button SW8:
      up = BUTTON4 (PA13, was wheel roll), down = BUTTON3 (PA16), centre push = BUTTON2 (PA14), left = BUTTON1 (PA21,
      BACK), right = BUTTON6 (PA3, new); FIRE stays SW9 = BUTTON5 (PA23).  All active low, common to GND.
  * J10: unpopulated 4-pin right-angle socket for a 0.91" 128 x 32 I2C OLED module (LCSC C5248081, GND VCC SCL SDA) as
    the alternative to the bonnet; same Pi I2C bus, same 3.3 V.
Stimulator (refs = the e-stim module's + 100): kbest rev E output stage, isolated by an ISO7741F (EN, CATH, RELEASE in,
FAULT_n back) and an ISO1640 (I2C to the DAC60501, readback kept: the DACx0501 has no SPI data-out pin), with
  * a 74HC4053 on +5 / -4.3 V for the sign / gate switches (was an ADG1436 on +/-15 V); its spare third switch inverts
    RELEASE for the SHORT switch
  * a DG418 (SPST, normally open, IN high = on) as the SHORT switch (was a DG419): closed while RELEASE is low
  * +/-V from the A0515S DC-DC (PS1, hand-fitted) or the battery pack (J102, B4B-PH-K-S), then an LC filter and a
    capacitance multiplier per rail, 20 V Zener clamps on each rail to GND_ISO (a floating GND_ISO can no longer take the
    switches past their 25 V ratings), TLV760 for +5V_ISO, a 4.3 V Zener for -5V_ISO (-4.3 V: the 4053 then sees <= 9.7 V worst case of its 10 V maximum).
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
HDR2RA = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal"
SOCK4RA = "Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Horizontal"
PH4 = "Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical"       # top entry: the pack's cable comes up past the tab
TP = "TestPoint:TestPoint_Pad_D1.0mm"
HOLE = "MountingHole:MountingHole_2.7mm_M2.5"
JUMPER_R = "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"
JUMPER_T = "Jumper:SolderJumper-2_P1.3mm_Open_TrianglePad1.0x1.5mm"
L0805 = "Inductor_SMD:L_0805_2012Metric"

# LCSC codes (0402 resistors and 0402 / 0603 capacitors are JLC basic parts)
L = dict(R100k="C25741", R10k="C25744", R1k="C11702", R47="C137973", R4k7="C25900", R2k2="C25879", R215k="C185443",
         R47k="C25792", R5k1="C25905", R2k="C4109", R3k9="C51721", R33="C25105", R100k01="C844674",
         R10k01="C95204", R2k49="C861299",
         C100n="C307331", C1u="C52923", C10n="C15195", C470n="C47339", C100p="C1546", C4u7="C69335",
         C1u50="C559769", C100n50="C14663", C1u50_0805="C726584", C10u="C15850", C22u="C12891",
         BAT54WS="C124205", Z4V3="C22399888", Z20="C173445", LEDW="C2290", LEDR="C2286",
         NPN="C20526", PNP="C53444", L10u="C139245",
         USBC="C2988369", JOY="C202415", TS1088="C720477", MSK="C431540", EEPROM="C283445", LDO="C632000",
         LOADSW="C110466", CH340="C2977777", MCU="C20618748", BUF="C80500", PFET="C471913", DUALPNP="C154733",
         ISO7741="C2872241", ISO1640="C5122339", TLV760="C2867465", DAC="C1852027", OPA="C2876419",
         HC4053="C6546", DG418="C2673514", TLV1702="C2870937", PH4="C131334")


def R(ref, val, a, b, fp=R0402, lcsc=""):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, fp=C0402, lcsc=""):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


PARTS = [
    # ================================================================ 1. Raspberry Pi header, USB-C, 5 V / 3.3 V
    # Samtec HLE SMD socket with pass-through holes (hand-fitted, as on the HAT): the Pi's header pins can reach a bonnet above
    dict(ref="J1", sym="GPIO_2x20", value="GPIO", fp="Footprints:Samtec_HLE-120-02-xxx-DV-BE-LC_2x20_P2.54mm_Horizontal", lcsc="",
         nets={"1": "+3V3_PI", "2": "+5V", "3": "I2C_SDA", "4": "+5V", "5": "I2C_SCL", "6": "GND", "7": None, "8": "PI_TXD",
               "9": "GND", "10": "PI_RXD", "11": None, "12": "MCU_PWR_EN", "13": None, "14": "GND", "15": None, "16": None,
               "17": "+3V3_PI", "18": "SWCLK", "19": None, "20": "GND", "21": None, "22": "SWDIO", "23": None, "24": None,
               "25": "GND", "26": None, "27": "ID_SDA", "28": "ID_SCL", "29": None, "30": "GND", "31": None, "32": None,
               "33": None, "34": "GND", "35": None, "36": "NRST", "37": "PI_TRIGGER", "38": None, "39": "GND", "40": None}),
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
    C("C12", "100nF", "+5V", "GND", lcsc=L["C100n"]),
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
    R("R1", "3.9k", "+3V3_PI", "ID_SDA", lcsc=L["R3k9"]) | {"dnp": True},
    R("R2", "3.9k", "+3V3_PI", "ID_SCL", lcsc=L["R3k9"]) | {"dnp": True},
    # ================================================================ 2. MCU, USB-UART, reset, BSL, buttons, LEDs, display socket
    dict(ref="U7", sym="MSPM0G3507", value="MSPM0G3507SRHBR", fp="stimhat:VQFN32_RHB_TEX", lcsc=L["MCU"],
         nets={"1": "I2C_SDA", "2": "I2C_SCL", "3": "NRST", "4": "MSPM0_3V3", "5": "GND", "6": "ROSC",
               "7": "BUTTON6", "8": None, "9": None, "10": "FAULT_H", "11": "EN_H", "12": "PI_RXD", "13": "PI_TXD",
               "14": "MCU_UART_TX", "15": "MCU_UART_RX", "16": "CATH_H", "17": "BUTTON4", "18": "BUTTON2", "19": "RELEASE_H",
               "20": "BUTTON3", "21": "SDA_H", "22": "BSL_INVOKE", "23": "SWDIO", "24": "SWCLK", "25": "BUTTON1", "26": "SCL_H",
               "27": "BUTTON5", "28": "LED_MCU", "29": "MCU_STIM_OUT", "30": "MCU_STIM_IN", "31": "PI_TRIGGER", "32": "VCORE",
               "33": "GND"}),
    R("R4", "100k 0.1%", "ROSC", "GND", lcsc=L["R100k01"]),
    C("C4", "470nF", "VCORE", "GND", lcsc=L["C470n"]),
    R("R3", "10k", "MSPM0_3V3", "NRST", lcsc=L["R10k"]),
    C("C3", "10nF", "NRST", "GND", lcsc=L["C10n"]),
    dict(ref="JP4", sym="Jumper2", value="RTS_NRST", fp=JUMPER_T, lcsc="", nets={"1": "NRST", "2": "CH340_RTS"}),
    dict(ref="U6", sym="CH340N", value="CH340N", fp=JEITA8, lcsc=L["CH340"],
         nets={"1": "USB_DP", "2": "USB_DM", "3": "GND", "4": "CH340_RTS", "5": "MSPM0_3V3", "6": "MCU_UART_RX", "7": "MCU_UART_TX", "8": "MSPM0_3V3"}),
    C("C17", "100nF", "MSPM0_3V3", "GND", lcsc=L["C100n"]),
    dict(ref="SW6", sym="SW_Push", value="TS-1088-AR02016", fp="Button_Switch_SMD:SW_SPST_TS-1088-xR020", lcsc=L["TS1088"],
         nets={"1": "BSL_INVOKE", "2": "MSPM0_3V3"}),
    dict(ref="D7", sym="LED", value="KT-0603R", fp=LED0603, lcsc=L["LEDR"], nets={"1": "D7_K", "2": "LED_MCU"}),
    R("R15", "2k", "D7_K", "GND", lcsc=L["R2k"]),
    dict(ref="SW7", sym="Joystick5", value="SKRHADE010", fp="stimhat:SW_ALPS_SKRHADE010", lcsc=L["JOY"],
         nets={"1": "BUTTON4", "2": "BUTTON2", "3": "BUTTON1", "4": "BUTTON6", "5": "GND", "6": "BUTTON3"}),
    dict(ref="SW9", sym="SW_Push", value="TS-1088-AR02016", fp="Button_Switch_SMD:SW_SPST_TS-1088-xR020", lcsc=L["TS1088"],
         nets={"1": "BUTTON5", "2": "GND"}),
    dict(ref="J10", sym="Conn_01x04", value="OLED 0.91 (GND VCC SCL SDA)", fp=SOCK4RA, lcsc="", dnp=True,
         nets={"1": "GND", "2": "+3V3_PI", "3": "I2C_SCL", "4": "I2C_SDA"}),
    # ================================================================ 3. BNC trigger in / stim out
    dict(ref="J6", sym="BNC", value="BNC TRIGGER IN", fp="Footprints:BNC_Amphenol_031-5540_031-5539_Dual", lcsc="",
         nets={"1": "BNC_IN", "2": "GND"}),
    dict(ref="J7", sym="BNC", value="BNC STIM OUT", fp="Footprints:BNC_Amphenol_031-5540_031-5539_Dual", lcsc="",
         nets={"1": "BNC_OUT", "2": "GND"}),
    R("R23", "1k", "BUF_IN", "BNC_IN", lcsc=L["R1k"]),
    R("R24", "100k", "BUF_IN", "GND", lcsc=L["R100k"]),
    dict(ref="U8", sym="74LVC2G17", value="74LVC2G17GW", fp=SOT363, lcsc=L["BUF"],
         nets={"1": "BUF_IN", "2": "GND", "3": "MCU_STIM_OUT", "4": "BUF_OUT", "5": "MSPM0_3V3", "6": "MCU_STIM_IN"}),
    R("R25", "33", "BNC_OUT", "BUF_OUT", lcsc=L["R33"]),
    dict(ref="D9", sym="LED", value="KT-0603R", fp=LED0603, lcsc=L["LEDR"], nets={"1": "STIM_LED_K", "2": "BUF_OUT"}),
    R("R18", "2k", "STIM_LED_K", "GND", lcsc=L["R2k"]),
    # ================================================================ 4. isolation (HAT side pulls, ISO7741F, ISO1640)
    R("R101", "100k", "EN_H", "GND", lcsc=L["R100k"]),
    R("R102", "100k", "CATH_H", "GND", lcsc=L["R100k"]),
    R("R103", "100k", "RELEASE_H", "GND", lcsc=L["R100k"]),
    R("R107", "4.7k", "MSPM0_3V3", "SDA_H", lcsc=L["R4k7"]),
    R("R108", "4.7k", "MSPM0_3V3", "SCL_H", lcsc=L["R4k7"]),
    dict(ref="U101", sym="ISO7741", value="ISO7741FDBQR", fp=SSOP16, lcsc=L["ISO7741"],
         nets={"1": "MSPM0_3V3", "2": "GND", "3": "RELEASE_H", "4": "EN_H", "5": "CATH_H", "6": "FAULT_H", "7": "MSPM0_3V3", "8": "GND",
               "9": "GND_ISO", "10": "+5V_ISO", "11": "FAULT_n", "12": "CATH", "13": "EN", "14": "RELEASE", "15": "GND_ISO", "16": "+5V_ISO"}),
    C("C101", "100nF", "MSPM0_3V3", "GND", lcsc=L["C100n"]),
    C("C102", "100nF", "+5V_ISO", "GND_ISO", lcsc=L["C100n"]),
    dict(ref="U109", sym="ISO1640", value="ISO1640BDR", fp=SOIC8, lcsc=L["ISO1640"],
         nets={"1": "MSPM0_3V3", "2": "SDA_H", "3": "SCL_H", "4": "GND", "5": "GND_ISO", "6": "SCL", "7": "SDA", "8": "+5V_ISO"}),
    C("C103", "100nF", "MSPM0_3V3", "GND", lcsc=L["C100n"]),
    C("C124", "100nF", "+5V_ISO", "GND_ISO", lcsc=L["C100n"]),
    R("R109", "4.7k", "+5V_ISO", "SDA", lcsc=L["R4k7"]),
    R("R110", "4.7k", "+5V_ISO", "SCL", lcsc=L["R4k7"]),
    # ================================================================ 5. isolated power
    dict(ref="PS1", sym="A0515S", value="A0515S-1WR3", fp="estim:DCDC_SIP6_A0515S", lcsc="", dnp=True,
         nets={"1": "+5V", "2": "GND", "6": "+V_RAW", "5": "GND_ISO", "4": "-V_RAW"}),
    C("C104", "4.7uF", "+5V", "GND", fp=C0603, lcsc=L["C4u7"]),
    dict(ref="J102", sym="Conn_01x04", value="B4B-PH-K-S(LF)(SN)", fp=PH4, lcsc="",
         nets={"1": "+V_RAW", "2": "GND_ISO", "3": "-V_RAW", "4": "GND_ISO"}),
    dict(ref="L101", sym="L", value="10uH", fp=L0805, lcsc=L["L10u"], nets={"1": "+V_RAW", "2": "+V_F"}),
    dict(ref="L102", sym="L", value="10uH", fp=L0805, lcsc=L["L10u"], nets={"1": "-V_RAW", "2": "-V_F"}),
    C("C105", "10uF", "+V_F", "GND_ISO", fp=C0805, lcsc=L["C10u"]),
    C("C106", "10uF", "GND_ISO", "-V_F", fp=C0805, lcsc=L["C10u"]),
    dict(ref="Q101", sym="Q_NPN_BEC", value="MMBT3904", fp=SOT23, lcsc=L["NPN"], nets={"1": "QB_P", "2": "+V_STIM", "3": "+V_F"}),
    R("R111", "4.7k", "+V_F", "QB_P", lcsc=L["R4k7"]),
    C("C107", "10uF", "QB_P", "GND_ISO", fp=C0805, lcsc=L["C10u"]),
    dict(ref="Q102", sym="Q_PNP_BEC", value="MMBT3906", fp=SOT23, lcsc=L["PNP"], nets={"1": "QB_N", "2": "-V_STIM", "3": "-V_F"}),
    R("R112", "4.7k", "-V_F", "QB_N", lcsc=L["R4k7"]),
    C("C108", "10uF", "GND_ISO", "QB_N", fp=C0805, lcsc=L["C10u"]),
    C("C109", "10uF", "+V_STIM", "GND_ISO", fp=C0805, lcsc=L["C10u"]),
    C("C110", "10uF", "GND_ISO", "-V_STIM", fp=C0805, lcsc=L["C10u"]),
    dict(ref="D103", sym="D_Zener", value="BZT52C20S", fp=SOD323, lcsc=L["Z20"], nets={"1": "+V_STIM", "2": "GND_ISO"}),
    dict(ref="D104", sym="D_Zener", value="BZT52C20S", fp=SOD323, lcsc=L["Z20"], nets={"1": "GND_ISO", "2": "-V_STIM"}),
    dict(ref="U104", sym="TLV760", value="TLV76050DBZR", fp=SOT23, lcsc=L["TLV760"], nets={"2": "+V_STIM", "1": "+5V_ISO", "3": "GND_ISO"}),
    C("C111", "1uF 50V", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L["C1u50"]),
    C("C112", "1uF 50V", "+5V_ISO", "GND_ISO", fp=C0603, lcsc=L["C1u50"]),
    R("R113", "4.7k", "-5V_ISO", "-V_STIM", fp=R0603, lcsc="C23162"),
    dict(ref="D102", sym="D_Zener", value="BZT52C4V3S", fp=SOD323, lcsc=L["Z4V3"], nets={"1": "GND_ISO", "2": "-5V_ISO"}),
    C("C113", "100nF", "GND_ISO", "-5V_ISO", lcsc=L["C100n"]),
    # ================================================================ 6. set-point: DAC60501 (I2C), inverter, 74HC4053
    dict(ref="U105", sym="DAC60501", value="DAC60501ZDGSR", fp=VSSOP10, lcsc=L["DAC"],
         nets={"1": "+5V_ISO", "2": "VSET_P", "3": None, "4": "GND_ISO", "5": "+5V_ISO", "6": "SCL", "7": "GND_ISO", "8": "SDA",
               "9": None, "10": "VREFIO"}),
    C("C114", "1uF", "VREFIO", "GND_ISO", lcsc=L["C1u"]),
    C("C115", "100nF", "+5V_ISO", "GND_ISO", lcsc=L["C100n"]),
    dict(ref="U106", sym="OPA2192", value="OPA2192IDGKR", fp=VSSOP8, lcsc=L["OPA"],
         nets={"3": "OA_IN", "2": "ISENSE", "1": "OA_OUT", "5": "GND_ISO", "6": "U5B_IN", "7": "VSET_N", "8": "+V_STIM", "4": "-V_STIM"}),
    R("R105", "10.0k 0.1%", "VSET_P", "U5B_IN", fp=R0603, lcsc=L["R10k01"]),
    R("R106", "10.0k 0.1%", "U5B_IN", "VSET_N", fp=R0603, lcsc=L["R10k01"]),
    C("C116", "100nF 50V", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L["C100n50"]),
    C("C117", "100nF 50V", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L["C100n50"]),
    # 74HC4053: switch 1 (S1 = CATH) picks VSET_P (0) / VSET_N (1) -> SW_P; switch 2 (S2 = EN) picks 0 V (0) / SW_P (1) -> V_IN;
    # switch 3 (S3 = RELEASE) picks +5V_ISO (0) / GND_ISO (1) -> SHORT_IN: the DG418 is on (electrode shorted) while RELEASE is low
    dict(ref="U107", sym="74HC4053", value="CD74HC4053PWR", fp=TSSOP16, lcsc=L["HC4053"],
         nets={"16": "+5V_ISO", "7": "-5V_ISO", "8": "GND_ISO", "6": "GND_ISO",
               "11": "CATH", "12": "VSET_P", "13": "VSET_N", "14": "SW_P",
               "10": "EN", "2": "GND_ISO", "1": "SW_P", "15": "V_IN",
               "9": "RELEASE", "5": "+5V_ISO", "3": "GND_ISO", "4": "SHORT_IN"}),
    C("C118", "100nF", "+5V_ISO", "GND_ISO", lcsc=L["C100n"]),
    C("C119", "100nF", "GND_ISO", "-5V_ISO", lcsc=L["C100n"]),
    # ================================================================ 7. output stage, SHORT switch, fault detector
    R("R114", "1k", "V_IN", "OA_IN", lcsc=L["R1k"]),
    C("C120", "100pF", "OA_IN", "GND_ISO", lcsc=L["C100p"]),
    R("R115", "47", "OA_OUT", "E1", lcsc=L["R47"]),
    R("R116", "2.49k 0.1%", "ISENSE", "GND_ISO", fp=R0603, lcsc=L["R2k49"]),
    C("C121", "1uF 50V", "E1", "E1_OUT", fp=C0805, lcsc=L["C1u50_0805"]),
    dict(ref="J101", sym="Conn_01x02", value="ELECTRODE E1/E2", fp=HDR2RA, lcsc="", nets={"1": "E1_OUT", "2": "ISENSE"}),
    dict(ref="TP101", sym="TestPoint", value="ISENSE", fp=TP, lcsc="", nets={"1": "ISENSE"}),
    dict(ref="TP102", sym="TestPoint", value="GND_ISO", fp=TP, lcsc="", nets={"1": "GND_ISO"}),
    dict(ref="U108", sym="DG418", value="DG418DY-T1-E3", fp=SOIC8, lcsc=L["DG418"],
         nets={"1": "ISENSE", "2": None, "3": "GND_ISO", "4": "+V_STIM", "5": "+5V_ISO", "6": "SHORT_IN", "7": "-V_STIM", "8": "E1"}),
    R("R117", "10k", "+V_STIM", "TH_P", lcsc=L["R10k"]),
    R("R118", "215k", "TH_P", "TH_N", lcsc=L["R215k"]),
    R("R119", "10k", "TH_N", "-V_STIM", lcsc=L["R10k"]),
    dict(ref="U110", sym="TLV1702", value="TLV1702AIDGKR", fp=VSSOP8, lcsc=L["TLV1702"],
         nets={"5": "TH_P", "6": "E1", "7": "FAULT_OC", "3": "E1", "2": "TH_N", "1": "FAULT_OC", "8": "+V_STIM", "4": "-V_STIM"}),
    R("R120", "10k", "FAULT_OC", "FAULT_n", lcsc=L["R10k"]),
    R("R121", "4.7k", "+5V_ISO", "FAULT_n", lcsc=L["R4k7"]),
    dict(ref="D101", sym="D", value="BAT54WS", fp=SOD323, lcsc=L["BAT54WS"], nets={"1": "FAULT_n", "2": "GND_ISO"}),
    C("C122", "100nF 50V", "+V_STIM", "-V_STIM", fp=C0603, lcsc=L["C100n50"]),
    C("C125", "100nF 50V", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L["C100n50"]),
    C("C126", "100nF 50V", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L["C100n50"]),
    # ================================================================ 8. mechanical
    dict(ref="MH1", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
    dict(ref="MH2", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
    dict(ref="MH3", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
    dict(ref="MH4", sym="MountingHole", value="M2.5", fp=HOLE, lcsc="", nets={}),
]

BY_REF = {p["ref"]: p for p in PARTS}
assert len(BY_REF) == len(PARTS), "duplicate reference"

# hand-fitted parts: populated by us, not by JLC (no LCSC code, out of the BOM and CPL); DNP parts are marked dnp=True above
HAND_FIT = {"J1", "J6", "J7", "J101", "J102"}
# nets on the isolated side of the barrier (for the board's isolation rule): everything the stimulator references to GND_ISO
ISOLATED_NETS = {"+V_RAW", "-V_RAW", "+V_F", "-V_F", "+V_STIM", "-V_STIM", "GND_ISO", "+5V_ISO", "-5V_ISO", "QB_P", "QB_N",
                 "EN", "CATH", "RELEASE", "FAULT_n", "SDA", "SCL", "VSET_P", "VSET_N", "U5B_IN", "SW_P", "V_IN", "OA_IN",
                 "OA_OUT", "ISENSE", "E1", "E1_OUT", "TH_P", "TH_N", "FAULT_OC", "VREFIO", "SHORT_IN"}
