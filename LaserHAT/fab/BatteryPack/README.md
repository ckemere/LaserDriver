# fab/BatteryPack — rev C (2026-10-27)

`BatteryPack_gerbers.zip` (F/B Cu, paste, silk, mask, edge; Excellon PTH + NPTH, map), `BatteryPack_bom.csv` and
`BatteryPack_cpl.csv` (JLC columns) from `BatteryPack/tools/make_fab.py`; renders `BatteryPack_top.png`,
`BatteryPack_bottom.png`.  Board 100 × 100 mm, 2-layer, 1.6 mm, three 3.5 × 22 mm strap slots.  Hand-fitted / not in
BOM-CPL: H1–H4 (holes).  Through-hole assembled by JLC: SW1 toggle, J7/J8 XT60 and J5/J6 XH pack sockets, J3 header, J1's shield legs.
Check rotations in the DFM preview (see BatteryPack/README.md).  Rev B (4S 18650 clips, two boards stacked) = commit 6fa6e9d.
