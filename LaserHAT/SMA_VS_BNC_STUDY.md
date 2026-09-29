# SMA instead of BNC on the HAT: would it let the e-stim module go single-sided?

> **Superseded 2026-09-28 (later the same day).** The BNCs stay. The e-stim module grows *south* instead, over the
> Pi's port edge: outline 26.5 × 36.5 mm (y 76–112.5), which routes single-sided on 4 layers (see
> `EStimDaughter/DESIGN_NOTES.md`, rev M3). The SMA schematic change (commit b6c5e68) was reverted. The numbers below
> are kept for the record.

Study only (2026-09-28). Nothing on either board was changed for it. All coordinates are HAT board coordinates (mm, y down).

## 1. The question

The e-stim module (`EStimDaughter/`, rev M2 with the fault detector) is 26.5 × 23.5 mm = 623 mm², 4 layers, SMD on both sides. JLC's Economic PCBA tier needs single-sided assembly. The module's east edge is capped at x = 127.5 because HAT BNC J6 (TRIG IN) starts at x ≈ 128. Smaller SMA jacks would push that limit east; the question is whether the extra width is enough for the isolated side of the module to fit on the top only.

## 2. What is there today

**HAT, east of the module (x > 127.5, y 76–100):**

| Item | Footprint / body | Extent |
|---|---|---|
| J6 TRIG IN (BNC, dual 031-5540 / 031-5539 footprint) | pin at (135.30, 87.55) | x 127.48–143.12, on-board y 79.56–100 |
| J7 STIM OUT (same) | pin at (150.60, 87.55) | x 142.78–158.41, y 79.56–100 |
| BNC buffer U8 74LVC2G17 and the BNC_IN / BNC_OUT tracks | short B.Cu runs from vias at (143.25, 69.75) and (149.5, 68.0) | around (147, 67) |
| SW6 BSL button | | x 136.2–142.3, y 73.2–76.8 |
| D7 / D9 LEDs, R15 / R18 | | x 158.7–164.1, y 75.8–82.0 |
| SW9 FIRE | | x 160.5–164.0, y 86.0–92.0 |
| MH4 | Ø2.7 + head | (161.5, 96.5); keep-out to x ≈ 158.5 |
| Logo, "TRIG IN" / "STIM OUT" silk | | logo x 151–163, y 60–74; silk y 76.3–78.7 |

Everything else on that side is low SMD or empty. The module's `DAUGHTERBOARD` keep-out on the HAT is x 108–123.5, y 80.5–92.5 (nothing needs to move for a wider module except SW6, which pokes 0.8 mm into y ≥ 76 and would sit under the module's edge).

**E-stim module (rev M2, courtyard bounding boxes from `tools/build_pcb.py`):**

| | Area |
|---|---|
| Module outline | 623 mm² (x 101–127.5, y 76–99.5) |
| Isolated domain (both sides) | 322 mm² |
| Isolated domain usable on top (PS1's body takes 77 mm²) | ≈ 245 mm² |
| Isolated-side SMD courtyards, top | 132 mm² (16 parts) → 54 % of the usable top |
| Isolated-side SMD courtyards, bottom | 191 mm² (31 parts) → 59 % of the bottom |
| HAT-side SMD (R1–R5, C1, C3) + U1 | ≈ 60 mm², in the fixed HAT strip |

At M1 (no fault detector) the SMD courtyards were 153 mm² top (15 parts) / 141 mm² bottom (27), all parts counted, and Freerouting finished the board; at M2 (+41 mm² of courtyard) the best of 27 placement seeds leaves 2 nets for hand-finishing. So with this tool chain **≈ 55 % courtyard fill of the isolated domain is the practical ceiling**, and 50 % is comfortable.

## 3. How much isolated top area a single-sided M2 needs

All 323 mm² of isolated-side courtyards on the top: at 50–55 % fill that is **590–650 mm² of isolated top area, against 245 mm² today (2.4–2.6×)**. Keeping the HAT strip (J8, J9, U1, the pulls: about 200 mm² incl. the 2 mm barrier) as it is, the module has to gain about **350–400 mm² of isolated area, i.e. 15–17 mm of extra width at the fixed 23.5 mm height: east edge at x ≈ 142–145**.

(The module cannot grow north: the OLED bonnet covers to y 74.7. It cannot grow south: the HAT edge is y 100.)

## 4. SMA options and how far each moves the module's east limit

KiCad library footprints (courtyard sizes):

| Jack | Courtyard | On-board depth | Notes |
|---|---|---|---|
| Amphenol 132289 edge-launch (SMD) | 17.6 × 11.2 (11.2 along the edge) | 3.1 mm | for 1.6 mm boards |
| Samtec SMA-J-P-H-ST-EM1 edge-launch (SMD) | 14.8 × 8.1 (8.1 along the edge) | 2.65 mm | for 1.57 mm boards; narrowest |
| Amphenol 901-143 right-angle (THT) | 8.7 wide × 16.4 (barrel out) | 8.8 mm (pin row 4.5 mm inside the edge, body 4.3 mm behind it) | **user's preference**; Mouser stocks it; no KiCad 3D model on this machine (the Molex 73251-2200 stands in) |
| Amphenol 132134 vertical (THT) | 8.4 × 8.4 | 8.4 mm | cable leaves upward |

MH4's keep-out sets the east end of the south edge at x ≈ 158.4; two jacks side by side go from there westwards.

| Option | Where the two jacks go | Module east limit | Isolated top area | Fill, single-sided M2 |
|---|---|---|---|---|
| **0** today: two BNCs on the south edge | x 127.5–158.4 | 127.5 | 245 mm² | (double-sided: 54 % / 59 %) |
| **A1** two Amphenol 132289 edge-launch, south edge | x 136.0–158.4 | ≈ 135.5 | ≈ 435 mm² | 74 % — no |
| **A2** two Samtec edge-launch, south edge | x 142.2–158.4 | ≈ 141.5 | ≈ 575 mm² | 56 % — just reaches the ceiling |
| **A2-RA** two 901-143 right-angle, south edge (bodies y 91–100) | x 141.0–158.4 | ≈ 140.5 | ≈ 560 mm² | 57 % — just reaches |
| **A3** two vertical 132134 in the SE corner | x 141.6–158.4, y 91.6–100 | ≈ 141 | ≈ 565 mm² | 57 % — just reaches |
| **B** one jack on the east edge at y ≈ 63–71 (next to U8; logo moves), the other at the SE corner (south edge, x 150.3–158.4) | | ≈ 149.5 | ≈ 760 mm² | 42 % — comfortable |
| **B-RA** the same with 901-143 right-angle jacks: TRIG IN on the east edge, pin row at x 160.5, body y 62.7–71.3; STIM OUT at the SE corner, pin row at y 95.5, body x 149.7–158.4 | | ≈ 149 | ≈ 750 mm² | 43 % — comfortable |
| **B'** keep the BNCs: vertical 031-5539 for TRIG IN at the NE (x ≈ 152–165, y ≈ 61–74, logo moves), right-angle 031-5540 STIM OUT stays at x 142.8–158.4 | | ≈ 142 | ≈ 575 mm² | 56 % — just reaches |

Notes on the table:
- Every A/B option puts the module over SW6 (BSL). SW6 would move north ~1 mm (to y ≤ 75) or under the module's edge; it is used only for bootloader recovery.
- In options A2/A3/B/B' the module's south edge between x 117 and the first jack is free, so J1 (electrode header) can move out of the BACK-button thumb zone (x 107–116), which is an open item today.
- Option B needs one SMA footprint on the east edge in the logo's place: the BNC_IN track then runs ~15 mm from U8's via at (143.25, 69.75) — shorter than today. It is the only option with real margin.
- SMA cables: the lab's BNC-terminated gear needs SMA-to-BNC adapters (~$5 each); the user's Amphenol 031-5539 stock goes unused except in B'.

## 4a. Decision 2026-09-28: both right-angle SMAs on the south edge, ≥ 5 mm apart (option C)

The east edge is out (Pi connectors on that side). With two Amphenol 901-143 on the south edge, STIM OUT hard against MH4's keep-out (courtyard x 149.7–158.4) and TRIG IN 5 mm west of it (courtyard x 136.0–144.7, pin rows at y 95.5, bodies y 91.2–100), the module can grow three ways:

| Module outline | Size | Isolated top area | Single-sided M2 fill |
|---|---|---|---|
| Rectangle beside the jacks, x 101–135.5 | 34.5 × 23.5 = 811 mm² (1.3×) | ≈ 435 mm² | 74 % — still double-sided |
| **Notched**: x 101–158 for y 76–90.5, x 101–135.5 for y 90.5–99.5 (jacks stay fully open) | ≈ 1130 mm² (1.8×) | ≈ 640 mm² | ≈ 50 % — single-sided works |
| Rectangle over the jacks, x 101–158 | 57 × 23.5 = 1340 mm² (2.15×) | ≈ 960 mm² | ≈ 34 % |

The overhanging rectangle relies on the module's underside sitting ≈ 11 mm above the HAT (socket + header) while the 901-143 body is ≈ 7 mm tall: it clears, but the SMA nuts are then turned right under the module's edge, and the module's bottom side over the jacks must stay bare. The notched outline avoids both and still has the ≈ 50 % fill that this tool chain routes. Everything east of x 127.5 that the module now covers is low SMD except SW6 (BSL, moves ~1 mm north or goes under the edge), the "TRIG IN / STIM OUT" silk, and MH4 (x ≥ 158.5, outside). The FIRE button and LEDs (x ≥ 158.7) stay clear. The laser module can use the same outline if it ever needs the room; the J8/J9 sockets don't move.

## 5. What single-sided buys

- JLC Economic PCBA instead of Standard: the extended-part fees and component costs are identical; the difference at 5–10 boards is roughly the Standard setup/stencil premium, tens of dollars per order. A 4-layer board is still allowed in Economic.
- Simpler hand rework, and a wider module makes a **2-layer** single-sided version plausible (the 2-layer attempt at M1 left 3 nets open on the 623 mm² outline).
- Against it: a HAT change to the hand-routed board (BNC footprints out, SMA in, SW6, silk, keep-out, BNC tracks), a full re-layout of the module (outline, barrier, ground planes, J1), and SMA adapters.

## 6. Recommendation

- **The fault detector does not need any of this.** M2 fits the present 26.5 × 23.5 mm double-sided outline; what is left is finishing two nets by hand.
- **If single-sided assembly is wanted, do option B**: one SMA on the HAT's east edge at y ≈ 63–71 (beside the BNC buffer), one on the south edge at the SE corner, module widened to x ≈ 149.5 (48.5 × 23.5 mm, 1140 mm²). That gives ≈ 42–43 % isolated-side fill, room to move J1 east of the BACK button, and a fair chance at a 2-layer module. With the right-angle Amphenol 901-143 (the user's preference, 2026-09-28) the jack bodies take 8.8 mm of board depth: on the east edge that is x 156.2–165 at y 62.7–71.3 (the logo moves west), at the SE corner x 149.7–158.4 at y 91.2–100 (clear of MH4 and FIRE); the module goes to x ≈ 149.
- **Do not choose A1**, and treat **A2 / A3 / B'** as marginal (≈ 56 % fill is where the autorouter already gives up on M2); they only make sense if the module is hand-placed and hand-routed.
- **If the BNC stock matters more than assembly tier, keep option 0.** Nothing in the M2 work forces a change.

Next step if B is chosen: I would (1) put the two SMA footprints on the HAT and move the logo/SW6/silk, re-route BNC_IN/BNC_OUT (short, local), extend the `DAUGHTERBOARD` keep-out and the outline marker to x 149.5, run DRC; (2) change `EStimDaughter/tools/build_pcb.py` (X1, domains, barrier, anchors) for the wider outline and rebuild single-sided; (3) add a NOTICE to `estim_interface/QUESTIONS.md` and update the spec's §2.
