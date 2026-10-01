# LaserHAT — JLCPCB order files

- Board: 65.1 × 57.0 mm, **2 layers**, 1.6 mm FR-4
- PCB quote: upload `LaserHAT_gerbers.zip`
- Assembly: `LaserHAT_BOM.csv` + `LaserHAT_CPL.csv`. 42 placements, 28 unique parts, sides: **Top**
- Check part rotations in JLC's placement preview; KiCad and JLC orientations differ for some packages.

## Hand-fitted (not in JLC's BOM or CPL; order and solder these ourselves)

- J1: GPIO (Samtec_HLE-120-02-xxx-DV-BE-LC_2x20_P2.54mm_Horizontal)
- J6: BNC TRIGGER IN (BNC_Amphenol_031-5540_031-5539_Dual)
- J7: BNC STIM OUT (BNC_Amphenol_031-5540_031-5539_Dual)
- J8: DB_POWER_TIMING (PinSocket_1x05_P2.54mm_Vertical)
- J9: DB_ANALOG (PinSocket_1x05_P2.54mm_Vertical)
- SW8: BACK (SW_Tactile_SPST_Angled_PTS645Vx39-2LFS)

## Not fitted (DNP)

- R1: 3.9k (R_0402_1005Metric)
- R2: 3.9k (R_0402_1005Metric)

Not parts (jumpers, holes, logo, test pads, padless footprints): G1, JP1, JP4, JP5, MH1, MH2, MH3, MH4
