# EStimDaughter — JLCPCB order files

- Board: 26.6 × 33.1 mm, **4 layers**, 1.6 mm FR-4
- PCB quote: upload `EStimDaughter_gerbers.zip`
- Assembly: `EStimDaughter_BOM.csv` + `EStimDaughter_CPL.csv`. 42 placements, 23 unique parts, sides: **Top**
- Check part rotations in JLC's placement preview; KiCad and JLC orientations differ for some packages.

## Hand-fitted (DNP in the schematic; not in BOM/CPL)

- PS1: A0515S-1WR3 (DCDC_SIP6_A0515S)

## No LCSC number and not DNP — not in BOM/CPL, nobody fits these yet

- J1: ELECTRODE E1/E2 (PinHeader_1x02_P2.54mm_Horizontal)
- J8: J8 power/timing (underside) (PinHeader_1x05_P2.54mm_Vertical)
- J9: J9 I2C/release (underside) (PinHeader_1x05_P2.54mm_Vertical)

Not parts (jumpers, holes, logo, test pads, padless footprints): TP1, TP2
