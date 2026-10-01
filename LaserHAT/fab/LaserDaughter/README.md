# LaserDaughter — JLCPCB order files

- Board: 26.6 × 23.6 mm, **4 layers**, 1.6 mm FR-4
- PCB quote: upload `LaserDaughter_gerbers.zip`
- Assembly: `LaserDaughter_BOM.csv` + `LaserDaughter_CPL.csv`. 23 placements, 20 unique parts, sides: **Top**
- Check part rotations in JLC's placement preview; KiCad and JLC orientations differ for some packages.

## Hand-fitted (not in JLC's BOM or CPL; order and solder these ourselves)

- J1: HAT_J8 (PinHeader_1x05_P2.54mm_Vertical)
- J2: Conn_02x02_Counter_Clockwise (PinHeader_2x02_P2.54mm_Vertical)
- J3: HAT_J9 (PinHeader_1x05_P2.54mm_Vertical)
- J5: RED_SHUNT (PinHeader_1x02_P2.00mm_Vertical)

## Not fitted (DNP)

- J4: PD_K-LASER_V (solder jumper) (SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm)
