# LaserDaughter — JLCPCB order files

- Board: 26.6 × 23.6 mm, **2 layers**, 1.6 mm FR-4
- PCB quote: upload `LaserDaughter_gerbers.zip`
- Assembly: `LaserDaughter_BOM.csv` + `LaserDaughter_CPL.csv`. 23 placements, 20 unique parts, sides: **Top**
- Check part rotations in JLC's placement preview; KiCad and JLC orientations differ for some packages.

## Hand-fitted (DNP in the schematic; not in BOM/CPL)

- J2: Conn_02x02_Counter_Clockwise (PinHeader_2x02_P2.54mm_Vertical)

## No LCSC number and not DNP — not in BOM/CPL, nobody fits these yet

- J1: HAT_J8 (PinHeader_1x05_P2.54mm_Vertical)
- J3: HAT_J9 (PinHeader_1x05_P2.54mm_Vertical)
- J5: RED_SHUNT (PinHeader_1x02_P2.00mm_Vertical)

Not parts (jumpers, holes, logo, test pads, padless footprints): J4, TP1
