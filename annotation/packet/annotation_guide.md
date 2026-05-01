# NanoBubbleEval — Annotation Guide (1 page)

You are the **second annotator** on a 40-record subset. Your annotations will
be compared against a separate annotator's labels to compute inter-annotator
agreement. **Annotate independently. Do not discuss decisions with the other
annotator until you are done.**

## What you are extracting

For each record in `iaa_subset.csv`, read the `abstract_or_summary` and fill
in the six fields below. Each field has three cells: **value**, **unit**, and
**evidence_quote**.

| Field | What it means | Example value | Example unit |
|---|---|---|---|
| `size` | Particle / bubble diameter or hydrodynamic size | `200` or `150-250` | `nm` |
| `zeta_potential` | Surface charge | `-12.5` | `mV` |
| `stability` | Persistence, lifetime, or shelf-life duration | `7` | `days` |
| `payload` | Drug, dye, gene, gas, or cargo loaded into the carrier | `doxorubicin` | *(leave blank)* |
| `loading_efficiency` | Encapsulation / loading percentage | `72.4` | `%` |
| `release_profile` | Release behavior described in text | `sustained release over 48 h` | *(leave blank)* |

`payload` and `release_profile` are text fields; their unit cells stay blank.

## The four rules (read these carefully)

1. **Abstract only.** Do not open the full paper. Do not search the web. If
   the abstract does not state it, it does not exist for this task.
2. **`NOT_REPORTED` if absent.** If the abstract does not state the field,
   write `NOT_REPORTED` in **all three** cells (value, unit, evidence_quote).
   Do not guess. Do not infer from the title. Do not extrapolate.
3. **Verbatim evidence quote.** The `evidence_quote` cell must be a substring
   copy-pasted from the abstract. If you cannot quote it, you cannot claim
   it -- write `NOT_REPORTED`.
4. **Ranges stay as ranges.** "150-250 nm" -> value=`150-250`, unit=`nm`.
   Do not average. Multiple distinct values reported separately -> pick the
   **primary characterization value**; note alternatives in `annotator_notes`.

## Ambiguity flag (one per record)

Set `ambiguity_flag` to one of:
- `direct` -- all values you reported are stated explicitly in the abstract.
- `inferred` -- one or more values required light inference (e.g., unit
  inferred from context).
- `uncertain` -- you are unsure of one or more decisions; flag in
  `annotator_notes`.

## Worked examples

**Example A.** Abstract: *"Lipid nanobubbles (185 +/- 22 nm, zeta potential
-18 mV) loaded with doxorubicin showed 81% encapsulation efficiency and
sustained drug release over 72 h."*

| field | value | unit | evidence_quote |
|---|---|---|---|
| size | 185 | nm | `185 +/- 22 nm` |
| zeta_potential | -18 | mV | `zeta potential -18 mV` |
| stability | NOT_REPORTED | NOT_REPORTED | NOT_REPORTED |
| payload | doxorubicin |  | `loaded with doxorubicin` |
| loading_efficiency | 81 | % | `81% encapsulation efficiency` |
| release_profile | sustained drug release over 72 h |  | `sustained drug release over 72 h` |

ambiguity_flag = `direct`

**Example B.** Abstract: *"We review nanobubble applications in water
treatment, including aeration, flotation, and biofilm removal."*

All six fields = `NOT_REPORTED`. ambiguity_flag = `direct` (the abstract
genuinely reports nothing of this kind; that is a valid annotation).

**Example C.** Abstract: *"The bubbles remained stable for several days at
room temperature."*

| field | value | unit | evidence_quote |
|---|---|---|---|
| stability | several days | NOT_REPORTED | `remained stable for several days` |

ambiguity_flag = `inferred` (no numeric value, qualitative duration only).

## Common pitfalls

- Do **not** confuse `payload` (what is loaded) with `release_profile`
  (how it comes out). They go in different rows even if the same sentence
  mentions both.
- For nanobubbles in environmental contexts (aeration, water treatment),
  `payload` is usually `NOT_REPORTED` -- do not invent oxygen as a payload
  unless the abstract names it.
- "approximately", "~", "around" are still direct values -- record the
  number, set ambiguity_flag = `direct`.
- A diameter expressed as "below 200 nm" -> value=`<200`, unit=`nm`,
  ambiguity_flag = `inferred`.
