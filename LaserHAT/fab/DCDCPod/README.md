# fab/DCDCPod - rev A (2026-10-29, layout turned around 2026-10-30)

`DCDCPod_gerbers.zip` (F/B Cu, paste, silk, mask, edge; Excellon PTH + NPTH, map), `DCDCPod_bom.csv` and
`DCDCPod_cpl.csv` (JLC columns) from `tools/make_fab.py`; renders `DCDCPod_top.png` (the parts face, which faces south
toward the HAT's BNC bodies when plugged in: PS1 along the top edge, J1 / J2 on the bottom edge),
`DCDCPod_bottom.png` (the bare back, which faces the OLED bonnet: title and test points TP1-TP3) and
`DCDCPod_perspective.png`.  Board 31 x 22.5 mm, 2-layer, **1.6 mm**, all SMD parts on the top.  Hand-fitted / not in
BOM-CPL: J1, J2, PS1 (right-angle headers and the A0515S), test points
TP1, TP2, TP3 (bare pads on the back).
Check the DFM preview for the SOT-23 and 0805 rotations (the CPL uses the Fabrication Toolkit's rotation table).
