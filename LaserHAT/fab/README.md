# JLCPCB order files: LaserHAT Rev 2 + output modules

`python tools/jlc_fab.py` regenerates everything here, using KiCad's bundled Python. Each board folder contains:
- `*_gerbers.zip`: for the PCB quote.
- `*_BOM.csv` and `*_CPL.csv`: for PCBA.
- Top and bottom renders.
- A README listing the hand-fitted parts.

| Board | Size | Layers | Assembled sides | Placements / unique parts | Extended parts | Hand-fit |
|---|---|---|---|---|---|---|
| `LaserHAT` | 65 × 57 mm | 2 | Top only | 44 / 29 | 15 | Pi header J1 (Samtec HLE-120-02-xxx-DV-BE), 2 module sockets, BACK button. BNCs J6/J7 are **DNP**: Amphenol 031-5540 / 031-5431 right-angle, or the vertical 031-5539 (dual footprint). |
| `LaserDaughter` | 26.5 × 23.5 mm | 2 | Top only | 23 / 20 | 13 | J1/J3 pin headers (underside), J5 RED shunt header |
| `EStimDaughter` | 26.5 × 36.5 mm (rev M3: 12.5 mm south overhang) | 4 | Top only | 54 / 29 | 21 | J8/J9 pin headers (underside), J1 electrode header; PS1 DC-DC is DNP |

The three boards share no extended parts, so across the whole order there are about 45 unique extended parts (the HAT's USB power switch added two). Basic parts carry no per-part fee.

**Before ordering**
- Check rotations in JLC's placement preview. The CPL is KiCad's own position export; a few packages differ between KiCad and JLC orientation, typically SOT-23-5/6, SOT-223, the USB-C connector and the BL-DT wheel.
- **HAT Pi header J1** is hand-fitted. Its footprint is a Samtec HLE-120-02-xxx-DV-BE bottom-entry socket. The Rev 1 LCSC number (C42411761, Harwin M20-7812045) doesn't fit it: Harwin's land pattern has its SMD pad rows 7.60 mm apart plus two Ø1.8 mm pegs, while the footprint's rows are 5.82 mm apart. Buy the Samtec part.
- **LCSC numbers** come from `tools/lcsc_parts.py` for the HAT and laser module, and from the e-stim module's own BOM. The Rev 1 LCSC fields in the HAT and laser schematics were largely wrong. Ignore them.

## Panelize or not?

**Recommendation: three separate designs in one order (one shipment). Don't combine them into a mixed panel.**

Reasons:
1. **A mixed panel inherits the most expensive specs.** The e-stim module needs 4 layers (single-sided assembly since rev M3). As one panel, the HAT area (about 3× the other two combined) would be built as 4-layer too. Ordered separately:
   - the HAT and laser module are 2-layer boards under 100 × 100 mm, JLC's cheapest PCB tier;
   - the e-stim module is a small 4-layer board.

   A combined panel (roughly 100 × 70 mm with rails) would be a 4-layer board of that size.
2. **Panelizing doesn't save the big assembly costs.** The extended-part fees are the same either way (43 unique parts, none shared). So is component cost. Panelizing mainly saves the per-order setup fee and stencil, twice. That is a few dollars on JLC's Economic tier and more on Standard.
3. **JLC treats several designs in one panel as a special case.** It adds a surcharge for multiple designs per panel. A merged BOM/CPL must also carry unique reference designators (these boards reuse R1, J1, etc.).
4. **Assembly tier.** Parts on both sides push an order to JLC's Standard PCBA tier; check the current terms.
   - The laser module is single-sided, so it can use Economic.
   - The HAT is single-sided too: R8/R10, the USB-C CC resistors, moved to the top.
   - The e-stim module is single-sided since rev M3 (all SMD on the top; only the headers and the DNP DC-DC are hand-fitted).

**When panelizing does make sense:** at larger quantities, panelize each design with itself (for example, the two 26.5 × 23.5 mm modules in 2 × 2 or 3 × 3 panels). JLC can do this for you ("panel by JLCPCB"), or KiKit can.

The quickest check is to quote each zip at your quantity (for example 5 or 10) with and without assembly, and compare with JLC's panel option.
