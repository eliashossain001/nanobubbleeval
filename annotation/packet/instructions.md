# NanoBubbleEval — IAA annotation task (1-day scope)

Thanks for helping with the second-annotator pass. This task fits in one
focused day and is the single most important external contribution to the
benchmark's credibility.

This file contains everything you need: the task scope, the decision rules,
worked examples, and the deliverable checklist. The only other file is the
spreadsheet `iaa_subset.csv`, which has 40 records to annotate.

---

## 1. What you are doing

You are the **second annotator** on a 40-record subset. Your annotations
will be compared against a separate annotator's labels to compute
inter-annotator agreement. **Annotate independently. Do not discuss
specific records or decisions with the other annotator until you are done.**

For each record in `iaa_subset.csv`, read the `abstract_or_summary` column
and fill in 20 empty cells per row.

## 2. The six fields you are extracting

Each field has three cells: **value**, **unit**, and **evidence_quote**.

| Field | What it means | Example value | Example unit |
|---|---|---|---|
| `size` | Particle / bubble diameter or hydrodynamic size | `200` or `150-250` | `nm` |
| `zeta_potential` | Surface charge | `-12.5` | `mV` |
| `stability` | Persistence, lifetime, or shelf-life duration | `7` | `days` |
| `payload` | Drug, dye, gene, gas, or cargo loaded into the carrier | `doxorubicin` | *(leave blank)* |
| `loading_efficiency` | Encapsulation / loading percentage | `72.4` | `%` |
| `release_profile` | Release behavior described in text | `sustained release over 48 h` | *(leave blank)* |

`payload` and `release_profile` are text fields; their unit cells stay blank.

## 3. The four rules (read carefully)

1. **Abstract only.** Do not open the full paper. Do not search the web.
   If the abstract does not state it, it does not exist for this task.
2. **`NOT_REPORTED` if absent.** If the abstract does not state the field,
   write `NOT_REPORTED` in **all three** cells (value, unit, evidence_quote).
   Do not guess. Do not infer from the title. Do not extrapolate.
3. **Verbatim evidence quote.** The `evidence_quote` cell must be a
   substring copy-pasted from the abstract. If you cannot quote it, you
   cannot claim it -- write `NOT_REPORTED`.
4. **Ranges stay as ranges.** "150-250 nm" -> value=`150-250`, unit=`nm`.
   Do not average. If multiple distinct values are reported separately,
   pick the **primary characterization value** and note the alternatives
   in `annotator_notes`.

## 4. Ambiguity flag (one per record)

Set `ambiguity_flag` to one of:
- `direct` -- all values you reported are stated explicitly in the abstract.
- `inferred` -- one or more values required light inference (e.g., unit
  inferred from context, or "below 200 nm" -> `<200`).
- `uncertain` -- you are unsure of one or more decisions; describe the
  ambiguity in `annotator_notes`.

## 5. Worked examples

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

All six fields = `NOT_REPORTED`. ambiguity_flag = `direct`. The abstract
genuinely reports nothing of this kind, and that is a valid, important
annotation -- do not feel pressure to fill cells.

**Example C.** Abstract: *"The bubbles remained stable for several days at
room temperature."*

| field | value | unit | evidence_quote |
|---|---|---|---|
| stability | several days | NOT_REPORTED | `remained stable for several days` |

All other fields = `NOT_REPORTED`. ambiguity_flag = `inferred` (no numeric
value, qualitative duration only).

## 6. Common pitfalls

- Do **not** confuse `payload` (what is loaded) with `release_profile`
  (how it comes out). They go in different rows even if the same sentence
  mentions both.
- For nanobubbles in environmental contexts (aeration, water treatment),
  `payload` is usually `NOT_REPORTED` -- do not invent oxygen as a payload
  unless the abstract names it explicitly.
- "approximately", "~", "around" still count as direct values -- record the
  number, set ambiguity_flag = `direct`.
- A diameter expressed as "below 200 nm" -> value=`<200`, unit=`nm`,
  ambiguity_flag = `inferred`.
- If a numeric value appears without a unit (e.g., "size of 200"), record
  the value, mark unit `NOT_REPORTED`, and set ambiguity_flag = `uncertain`.

## 7. Workflow

1. Read this file once end-to-end (~10 min).
2. Open `iaa_subset.csv` in Excel / LibreOffice / a CSV editor. There are
   40 rows. Each row has `title`, `year`, `journal_or_venue`,
   `document_type`, `nanobubble_vs_nanoparticle`, `application_category`,
   and `abstract_or_summary`.
3. For each row, fill the 20 empty annotation columns:
   - 6 fields x 3 cells = 18 cells (value, unit, evidence_quote)
   - `ambiguity_flag` (`direct` / `inferred` / `uncertain`)
   - `annotator_notes` (free text; only when something is ambiguous)
4. Save as `iaa_subset_<your-initials>.csv` and email it back.
5. In your reply, include a **5-line note** listing any records or fields
   where the rule was unclear. These edge cases are valuable for refining
   the full annotation guideline.

## 8. Time budget

- Expected total: **7-9 hours of focused work**.
- Average per record: ~12-14 minutes.
- If you are running short on time: **fully annotate the first N records**
  rather than partially annotating all 40. A clean partial set is more
  useful than a noisy full set.

## 9. Critical rules (one more time)

- **Annotate independently.** Do not look at the other annotator's labels
  or discuss specific records before submitting.
- **Abstract only.** Do not open the full paper or search the web.
- **`NOT_REPORTED` is a valid and important answer.** Many records will
  have several `NOT_REPORTED` cells. That is correct and expected.
- **Evidence quote must be verbatim.** If you cannot copy-paste the phrase
  from the abstract, the field is `NOT_REPORTED`.

## 10. Deadline

End of **[DAY, DATE]**. If you hit a blocker before that, message me --
a quick clarification is much better than guessing.

## 11. Deliverable checklist

- [ ] Filled `iaa_subset_<your-initials>.csv` (40 rows, 20 annotation columns each)
- [ ] 5-line note on ambiguous records / unclear rules
- [ ] Confirmation that you did not consult external sources or another
      annotator's labels
