# EStimDaughter — JLCPCB order files

- Board: 26.6 × 33.1 mm, **4 layers**, 1.6 mm FR-4
- PCB quote: upload `EStimDaughter_gerbers.zip`
- Assembly: `EStimDaughter_BOM.csv` + `EStimDaughter_CPL.csv`. 42 placements, 23 unique parts, sides: **Top**
- Check part rotations in JLC's placement preview; KiCad and JLC orientations differ for some packages.

## Hand-fitted (no LCSC number, excluded from the position file; not placed by JLC)

- J1: ELECTRODE E1/E2 (PinHeader_1x02_P2.54mm_Horizontal)
- J8: J8 power/timing (underside) (PinHeader_1x05_P2.54mm_Vertical)
- J9: J9 I2C/release (underside) (PinHeader_1x05_P2.54mm_Vertical)

## Not fitted (DNP)

- PS1: A0515S-1WR3 (DCDC_SIP6_A0515S)

Not parts (jumpers, holes, logo, test pads, padless footprints): TP1, TP2
