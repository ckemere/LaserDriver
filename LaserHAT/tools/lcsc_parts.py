"""LCSC / JLCPCB part assignments for machine assembly, per board (checked against the JLC parts library
2026-09-26 with EStimDaughter/tools/jlc_search.py and lcsc_check.py).

These tables are authoritative.  `tools/stamp_lcsc.py` writes them into the "LCSC Part #" field of every
schematic symbol and board footprint (the field KiCad's Fabrication Toolkit reads), removing the misspelt
Rev 1 variants ("LCSC Part#", "LCSC Parth#", "LCSC Part"), and applies VALUES below; tools/jlc_fab.py
uses the tables and warns when a board field disagrees.  Re-run stamp_lcsc.py after editing this file.
The e-stim module keeps its own list in EStimDaughter/bom_EStimDaughter.csv.
Re-verified against LCSC / JLC on 2026-09-30 (MPN, package and value of every code).

Parts not listed are hand-fitted (through-hole connectors, buttons, headers) or not parts at all
(solder jumpers, mounting holes, logo, test pads); jlc_fab.py lists them in each board's README.
"""

HAT = {
    # capacitors
    "C1": "C307331", "C6": "C307331", "C12": "C307331", "C15": "C307331", "C16": "C307331",  # 100nF 0402 (basic)
    "C13": "C52923",     # 1uF 0402 (basic)
    "C2": "C15850",      # 10uF 25V 0805 (basic)
    "C3": "C15195",      # 10nF 0402 (basic)
    "C4": "C47339",      # 470nF 0402
    # LEDs, 0603, JLC basic (Rev 1 used an extended emerald green, C5336487).  Only red and white are
    # basic; the MCU/STIM LEDs are driven from 3.3 V so they must be red (Vf 2.4 V); the 5 V rail LED is white.
    "D5": "C2290",               # KT-0603W white (5V rail)
    "D7": "C2286", "D9": "C2286",  # KT-0603R red (MCU, STIM)
    # resistors 0402 1 %
    "R1": "C51721", "R2": "C51721",          # 3.9k
    "R3": "C25792", "R21": "C25792",         # 47k (basic)
    "R4": "C844674",                          # 100k 0.1 %
    "R7": "C25744", "R22": "C25744",         # 10k (basic)
    "R8": "C25905", "R10": "C25905",         # 5.1k USB-C CC (basic)
    "R13": "C4109",                           # 2k (basic): D5 series resistor, was 3k (extended); same as R15/R18
    "R15": "C4109", "R18": "C4109",          # 2k (basic)
    "R19": "C25900", "R20": "C25900",        # 4.7k (basic)
    "R23": "C11702",                          # 1k (basic)
    "R24": "C25741",                          # 100k (basic)
    "R25": "C25105",                          # 33R (basic)
    # semis / ICs / misc
    "Q3": "C471913",     # AP30P30Q, PDFN3333 P-FET, 13 mOhm max @ -4.5 V (ideal diode)
    "Q4": "C154733",     # DMMT5401-7-F
    "U1": "C283445",     # M24C32-WDW6TP, TSSOP-8 (HAT ID EEPROM; CAT24C32 C94264 is out of stock; pin-compatible)
    "U4": "C632000",     # MCP1700T-3302E/MB
    "U5": "C110466",     # AP2171WG-7, SOT-25 (= SOT-23-5); the DWG-7 C2680322 has ~250 in stock
    "U6": "C2977777",    # CH340N
    "U7": "C20618748",   # MSPM0G3507SRHBR
    "U8": "C80500",      # 74LVC2G17GW,125 (Nexperia)
    "J5": "C2988369",    # G-Switch GT-USB-7010ASV (matches the footprint; Rev 1 field pointed elsewhere)
    "SW6": "C720477",    # TS-1088 (BSL)
    "SW7": "C53223909",  # SHOUHAN BL-DT thumbwheel
    "SW9": "C720477",    # TS-1088 (FIRE), same as SW6
    "SW10": "C431540",   # SHOU HAN MSK12C02 right-angle slide switch (USB power; gate drive only)
    "Q5": "C471913",     # AP30P30Q, PDFN3333 P-FET: USB VBUS power switch
    "R26": "C25741",     # 100k (basic): Q5 gate pull-up
}

# Schematic Value strings that stamp_lcsc.py sets so the BOM reads the same as the part ordered.
VALUES = {
    "HAT": {"U1": "M24C32-WDW6TP", "R13": "2k", "U5": "AP2171W"},
    "LASER": {},
}

LASER = {
    "C11": "C15195",     # 10nF 0402 (basic)
    "C12": "C307331",    # 100nF 0402 (basic)
    "C8": "C12891", "C9": "C12891",      # 22uF 25V 1206 (basic)
    "D1": "C37049", "D3": "C37049",      # DSK14, 1A 40V Schottky SOD-123FL (SS14FL is out of stock)
    "D2": "C209582",     # KDZVTR2.4B 2.4V 1W SOD-123FL (ROHM)
    "D4": "C209583",     # KDZVTR2.7B 2.7V 1W SOD-123FL (ROHM)
    "L1": "C503307",     # Bourns SRN4018-100M, 10uH, Isat 1.4A
    "Q1": "C3290118",    # SI3134KDWA-TP
    "Q2": "C274612",     # NDT3055L (onsemi)
    "R1": "C25741",      # 100k (basic)
    "R2": "C25779",      # 33k (basic)
    "R3": "C25783",      # 39k
    "R4": "C25744", "R6": "C25744",      # 10k (basic)
    "R5": "C25761",      # 187k
    "R11": "C852624",    # 1k 0.1 %
    "R12": "C25900",     # 4.7k (basic)
    "Rs1": "C2105197",   # ROHM ESR18EZPF2R00, 2R 1 % 0.5 W 1206
    "SW5": "C221841",    # PCM12SMTR
    "U2": "C84817",      # MT3608
    "U3": "C55940",      # TLV2371IDBVR
}
