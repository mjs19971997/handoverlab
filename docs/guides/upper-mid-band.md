# How to study handover in the upper mid-band (FR3)

The upper mid-band (FR3, about 7 to 24 GHz) is the range 3GPP studies for 5G-Advanced and beyond;
TR 38.901 was re-examined for it in Rel-19. HandoverLab's default world already sits at its lower
end (10 GHz). The built-in scenario [`fr3-urban-15ghz`](../scenarios/fr3-urban-15ghz.md) (since
1.0.0rc2) moves the same world to 15 GHz with a 400 MHz carrier and an antenna array of the same
size, so that a rule can be compared across the band with everything else held equal.

## 1. One rule set, two carriers

```yaml
# fr3.yaml
schema: 1
scenario: fr3-urban-15ghz
seeds: [1, 2, 3]
rules:
  - {rule: a3, off_db: 3.0, ttt_s: 0.16}
  - {rule: cho, o_prep_db: -2.0, o_exec_db: 3.0, ttt_exec_s: 0.08}
  - {rule: ltm, o_prep_db: -3.0, o_switch_db: 2.0}
output: results/fr3-15ghz.csv
```

```bash
handoverlab run fr3.yaml
```

Then set `scenario: urban-grid-10ghz` and run it again with `--output results/fr3-10ghz.csv`: the
same seeds give the same users, services and site plan at both carriers. Or, in one study, as a
condition (paired by seed; add `radio.carrier_ghz` to `tuning.group_by` for one tuning per carrier):

```yaml
scenario: {base: urban-grid-10ghz}
conditions:
  radio.carrier_ghz: [10.0, 15.0]
```

A study condition changes only the key it names. To move the whole `fr3-urban-15ghz` set-up
(carrier, bandwidth and beam gain together), use it as the base of a second study or vary the keys
together in your own scenario files.

## 2. What to expect and what to check

- At 15 GHz the path loss is about 3.5 dB higher and the noise 3 dB higher (twice the bandwidth),
  while the larger array gains 3.5 dB: the signal-to-noise ratio drops by about 3 dB. Interference
  scales with the signal, so `sinr_db` falls less where the cells are interference-limited.
- Compare `failures_pm` and `unnecessary_pm` between the carriers for the same rule, not their
  absolute values (the absolute failure level is not calibrated: it was checked against ns-3 only on
  `ns3-urban-3.5ghz`, where the ns-3 comparison setting gives 0.5-1.3 times ns-3's level and passes the
  pre-registered checks on none of three fresh sets; see
  [calibration](../calibration.md#correction-in-260-equal-run-lengths)).
- If a rule tuned at 10 GHz loses at 15 GHz, tune it per carrier (`group_by: [radio.carrier_ghz]`)
  before drawing conclusions: an untuned baseline makes any other rule look good.

## 3. Other points in the band

Use the card as a base and override the carrier and the matching values:

```yaml
scenario: {base: fr3-urban-15ghz, radio: {carrier_ghz: 22.0, bs_gain_db: 26.8}}
```

(26.8 dB = 20 + 20 log10(22/10) for an array of fixed size.) See
[add a scenario](add-scenario.md) to give such a variant its own card.

## Limits

The TR 38.901 UMi street-canyon formulas are used as they are; frequency-dependent penetration,
foliage and body loss are not modelled, and the abstraction has no fast fading. The card lists
these limits with the source of every value.
