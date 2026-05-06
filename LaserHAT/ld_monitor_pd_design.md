# Laser Diode Monitor Photodiode — Design Reference

## 1. Package Variant Reference

The eight standard laser diode package styles are shown below. Five of the eight include an integrated monitor photodiode (PD). The remaining three contain only the laser diode (LD).

![Laser Diode Package Styles A–H](ld_package_styles.png)

### 1.1 Pin / Connection Table

| Style | Has PD | LD Anode | LD Cathode | PD Anode | PD Cathode | Case / Common Node | Notes |
|-------|--------|----------|------------|----------|------------|--------------------|-------|
| **A** | ✅ | Pin | = Case | = Case | Pin | LD− = PD+ | Anti-series; case is mid-node |
| **B** | ✅ | = Case | Pin | Pin | = Case | LD+ = PD− | Anti-series; case is high-side |
| **C** | ✅ | Pin | = Case | = Case | Pin | LD− = PD+ | Electrically identical to Style A; different LD symbol |
| **D** | ✅ | = Case | Pin | Pin | = Case | LD+ = PD− | Electrically identical to Style B |
| **E** | ❌ | Pin | Pin | — | — | Separate / floating | No PD |
| **F** | ✅ | Pin | = Case | Pin | = Case | LD− = PD− | **Common cathode** — most convenient topology |
| **G** | ❌ | Pin | Pin (dot) | — | — | Cathode marked by dot | No PD |
| **H** | ❌ | Pin | = Case | — | — | Case = Cathode | No PD; case-grounded |

> **Symbol note:** In the image, Styles A and C share the same pinout but differ only in the LD schematic symbol (edge-emitting vs. arrow-style). Similarly, Styles B and D are electrically identical.

---

## 2. PCB Header Description

The PCB exposes the following header and jumper:

| Designator | Signal | Description |
|------------|--------|-------------|
| `LD_A` | LD Anode | Positive terminal of the laser diode |
| `LD_K` | LD Cathode | Negative terminal of the laser diode; connects to low-side current source |
| `PD_A` | PD Anode | Positive terminal of the monitor photodiode |
| `PD_K` | PD Cathode | Negative terminal of the monitor photodiode |
| `JP1` | LD_K — PD_A short | **Install** when LD cathode and PD anode are *not* internally connected in the package; **leave open** when they are already shorted internally (Styles A/C) |

The low-side current source (LSCS) is modulated and sinks current from `LD_K` to GND. The supply rail `Vcc` feeds the LD anode through whatever series impedance the driver requires.

---

## 3. Wiring by Package Style

### 3.1 Style F — Common Cathode ✅ (Recommended)

**Internal connections:** `LD_K = PD_K = Case`

**JP1:** Leave open (LD_K and PD_K are already shorted internally; PD_A is an independent pin)

```
Vcc ────────────────────── LD_A  (header)
                                │
                           [Laser Diode]
                                │
GND ←── [LSCS] ←── LD_K = PD_K (header / Case)
                                │
                           [Monitor PD]
                                │
        ADC ─── [R_sense] ─── PD_A  (header)
                │
               GND
```

- The PD cathode sits at the LSCS compliance voltage (~0.3–0.5 V above GND), providing a small but adequate reverse bias
- `V_ADC = I_PD × R_sense`
- The ADC input is near GND — ideal for standard 3.3 V microcontroller ADC inputs
- For a slow APC loop, low-pass filter the ADC reading to average out modulation-induced compliance voltage variation

**Sense resistor sizing:** Target `V_ADC ≈ 1–2 V` at maximum operating photocurrent. With `I_PD ≈ 500 µA` (typical at 50 mW, ~2% rear-facet coupling, 0.5 A/W responsivity), use **R_sense = 2.2–4.7 kΩ**.

---

### 3.2 Styles B / D — Common Anode (High-Side Case) ✅

**Internal connections:** `LD_A = PD_K = Case`

**JP1:** Leave open (LD_A and PD_K are already shorted internally; LD_K and PD_A are independent pins)

```
Vcc ────────────────────── LD_A = PD_K (header / Case)
                           │              │
                      [Laser Diode]  [Monitor PD]
                           │              │
GND ←── [LSCS] ←── LD_K (header)   PD_A (header)
                                         │
                               [R_sense]
                                         │
                               GND ──── ADC input
```

- The PD cathode (= Case) sits at Vcc — a stable, noise-free high rail
- The PD is reverse-biased by nearly the full `Vcc` — excellent linearity and speed
- `V_ADC = I_PD × R_sense`, referenced cleanly to GND
- This is the **cleanest topology for a resistor + ADC sense** circuit because the PD bias is independent of LSCS compliance voltage

**Sense resistor sizing:** Same as Style F above. With Vcc = 3.3 V, the ADC clips when `I_PD > Vcc / R_sense`; at R = 4.7 kΩ this clips at ~700 µA, which is ample headroom.

---

### 3.3 Styles A / C — Anti-Series, LD− = PD+ = Case ⚠️ (Awkward)

**Internal connections:** `LD_K = PD_A = Case`

**JP1:** Install to connect header `LD_K` to `PD_A` (they are already internally connected, but the jumper ties both header pins together to the Case node)

```
Vcc ─── LD_A  (header)
              │
         [Laser Diode]
              │
   LD_K = PD_A = Case  (header, both pins shorted by JP1 or internal)
              │
          [LSCS] ── GND
              │
         [Monitor PD]
              │
         PD_K  (header)  ──── ????
```

The **PD anode is at the LSCS compliance node** (~0.3–0.5 V above GND). The PD cathode (`PD_K`) is the only free terminal.

Placing `R_sense` between `PD_K` and `Vcc` gives `V_PD_K = Vcc − I_PD × R_sense` — a near-rail voltage that most microcontroller ADC inputs handle poorly (common-mode range typically limited to `Vcc`).

A direct resistor-to-GND sense on `PD_K` is not viable because the PD's reverse bias would then be negative (anode above cathode) at any meaningful photocurrent, forward-biasing the junction and making the measurement meaningless.

**Practical solutions for this style:**
- Use a **TIA with a virtual ground bootstrapped to the LSCS compliance node** (op-amp negative input referenced to `LD_K`), per Graeme, *Photodiode Amplifiers* (Butterworth-Heinemann, 1996), Ch. 3
- Add a **small negative supply** (e.g., −1.5 V charge pump) to properly reverse-bias `PD_K` below the Case node, then use a conventional TIA referred to GND
- Accept the degraded operating point and use photovoltaic mode (zero-bias TIA), at the cost of slower response and reduced linearity

---

### 3.4 Styles E, G, H — No Monitor PD

No sense circuit is possible with the package alone. If automatic power control (APC) is required, options include:

- **External beam-tap PD:** Insert a partial reflector in the optical path with a discrete photodiode
- **Front-facet monitoring:** Use a fibre-coupled or free-space PD on the output beam
- **Forward voltage proxy:** At constant current, monitor `V_LD` as an indirect indicator of temperature-induced power drift — coarse, suitable only for slow thermal compensation (see IEC 60747-5-5)

---

## 4. Sense Resistor Sizing Summary

| Parameter | Typical Value | Notes |
|-----------|--------------|-------|
| PD responsivity (Si) | 0.3–0.8 A/W | Check datasheet |
| Rear-facet monitor coupling | 1–5% | Package-dependent |
| `I_PD` at 50 mW optical | ~500 µA | At 0.5 A/W, 2% coupling |
| `I_PD` at 10 mW optical | ~100 µA | |
| Target `V_ADC` | 1.0–2.5 V | Within 3.3 V ADC range |
| Recommended R_sense (50 mW) | 2.2–4.7 kΩ | Verify against actual `I_PD` |
| Recommended R_sense (10 mW) | 10–22 kΩ | |
| **Maximum R_sense (Style F)** | `V_compliance / I_PD` | Forward bias limit — ~100 kΩ only safe below ~5 µA |
| ADC RC bandwidth | `1 / (2π × R × C_PD)` | C_PD typically 20–100 pF; 4.7 kΩ → ~340 kHz |

> **100 kΩ caution:** With typical photocurrents in the 100–500 µA range, 100 kΩ produces 10–50 V across the resistor — far outside ADC range. For Style F it also forward-biases the PD junction at currents above ~5 µA. Only use 100 kΩ if the photocurrent has been confirmed to be below ~10 µA.

---

## 5. APC Loop Integration

Once the photocurrent is available as a voltage on the ADC:

```
Setpoint ──(+)──► Error Amp ──► PI Compensator ──► LSCS Control Input
              ▲
         ADC reading
         (I_PD × R_sense)
         [low-pass filtered]
```

Keep the APC loop bandwidth **well below the modulation frequency** to prevent the loop from counteracting the intended modulation. For a digitally-controlled LSCS with ADC feedback, a loop bandwidth of 1–100 Hz is typical for APC against slow thermal drift, while the modulation may run at kHz–MHz rates.

**Key references:**
- Coldren & Corzine, *Diode Lasers and Photonic Integrated Circuits* (Wiley), Ch. 5 — APC loop dynamics
- Graeme, *Photodiode Amplifiers: Op Amp Solutions* (Butterworth-Heinemann, 1996) — TIA design
- TI Application Report SBOA035 — Transimpedance amplifier design
- Hobbs, *Building Electro-Optical Systems* (Wiley, 2000), §4.4 — High-side PD circuits
- IEC 60825-3 — Safety-related laser power monitoring requirements
