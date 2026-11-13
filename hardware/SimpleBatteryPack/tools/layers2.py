#!/usr/bin/env python3
"""SimpleBatteryPack to 2 copper layers (2026-11-01: JLC ships 2-layer boards much faster), idempotent:
F.Cu = parts and routing, B.Cu = the 0V plane (a pour over the whole board, 0.5 mm in from the edge) with as little
routing as the router leaves there.  Replaces tools/layers4.py (In1 = 0V plane, In2 = the gauges' GND / +GB rail pours):
the inner-layer zones go, the rails become tracks.  Rule areas (Pi / case standoffs) are set to both copper layers.
Copper is left alone; rip and route with tools/autoroute.py afterwards.     $KICAD_PY tools/layers2.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "SimpleBatteryPack.kicad_pcb")

b = pcbnew.LoadBoard(BOARD)
inner = [z for z in b.Zones() if not z.GetIsRuleArea() and not (z.IsOnLayer(pcbnew.F_Cu) or z.IsOnLayer(pcbnew.B_Cu))]
for z in inner:
    print("removed zone", z.GetZoneName() or z.GetNetname(), b.GetLayerName(z.GetLayer()))
    b.Remove(z)
stray = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu)]
for t in stray:
    b.Remove(t)
if stray:
    print("removed", len(stray), "inner-layer tracks")
if b.GetCopperLayerCount() != 2:
    b.SetCopperLayerCount(2)
    print("copper layers: 2")
both = pcbnew.LSET.AllCuMask(2)
for z in b.Zones():
    if z.GetIsRuleArea() and z.GetLayerSet() != both:
        z.SetLayerSet(both)
pour = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "0V" and z.IsOnLayer(pcbnew.B_Cu)]
if not pour:                                            # the B.Cu 0V plane: whole board, 0.3 mm clearance, thermals
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(b.FindNet("0V"))
    z.SetZoneName("0V pour")
    o = z.Outline(); o.NewOutline()
    for x, y in ((0.5, 0.5), (99.5, 0.5), (99.5, 99.5), (0.5, 99.5)):
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    z.SetLocalClearance(pcbnew.FromMM(0.3)); z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.3)); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.6))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z)
    print("added the B.Cu 0V pour")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(BOARD, b)
print("saved", BOARD, "copper layers", b.GetCopperLayerCount())
