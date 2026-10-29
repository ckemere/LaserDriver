# fab/DCDCPod - rev A (2026-10-29)

`DCDCPod_gerbers.zip` (F/B Cu, paste, silk, mask, edge; Excellon PTH + NPTH, map), `DCDCPod_bom.csv` and
`DCDCPod_cpl.csv` (JLC columns) from `tools/make_fab.py`; renders `DCDCPod_top.png` (the side facing north on the HAT)
and `DCDCPod_bottom.png`.  Board 31 x 19.5 mm, 2-layer, **1.2 mm** (keeps the back 0.7 mm clear of the HAT's BNC bodies;
1.6 mm also fits, with 0.3 mm), all SMD parts on the top.  Hand-fitted / not in BOM-CPL: J1, J2, PS1
(right-angle headers and the A0515S), test points TP1, TP2, TP3 (bare pads on the back).
Check the DFM preview for the SOT-23 and 0805 rotations (the CPL uses the Fabrication Toolkit's rotation table).
