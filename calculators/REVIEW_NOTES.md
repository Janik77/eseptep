# Calculator validation and arithmetic review

## Scope and provenance

Base: `ed3e6cd519cbf08ee2c5f9d070ab1f2018023b81`, also fetched `origin/main`
at the start of this work. Open PR metadata inspected: #34, #37, #43, #45,
#61 (broad older MVP changes). No repository AGENTS.md or .agents skills were
present. `ui/professional-interface` / `c2c03f9` was not available or reviewed.
No changes to projects, configuration, production, or customer data.

## Shared validation contract for project integration

`calculators.validation.validate_fields(fields, data)` returns a new dictionary
of normalized strings or raises `InputValidationError` whose `.errors` maps field
names to understandable Russian messages. It never mutates the raw input.
`validate_calculator_input(calculator, data)` additionally validates a supplied
variant. `calculate_materials` uses this boundary too, so direct callers must
supply all required fields; defaults belong only to a new/unbound UI form.

Required numbers must be finite and inside inclusive bounds; comma decimals
are accepted, fractions are rejected for integer fields, and up to two decimal
places are accepted to match persisted model precision. Values are not clamped,
truncated, or replaced with defaults. Choices must occur in their field's options.
An absent optional variant uses the calculator's default; a supplied empty or
unknown variant is an error. HTTP handlers retain original submitted inputs and
render field errors without calculating or persisting. The projects owner can
adopt this contract or an equivalent local validator; this change does not edit
or validate the project upload workflow.

Provisional **application limits**, not engineering rules: area 1–10,000 m²,
counts 1–100, thickness 0.1–20 cm. The thickness bounds already existed in field
metadata. The new upper area/count bounds keep inputs and amounts manageable
within storage precision. They require product review for larger projects.

## Arithmetic correction and concrete reproduction

Baseline stretch ceiling, area 20 m², one room, Economy:

- Existing rows before balancing sum to ₸103,600.
- Preset target: ₸53,700.
- `_adjust_variant_rows_total` chose the quantity-one niche and subtracted
  ₸49,900 from its ₸6,000 cost, yielding **−₸43,900**.

The corrected result uses the existing quantity and unit price: niche ₸6,000,
materials total **₸103,600**. It neither clamps negative amounts nor invents a
replacement coefficient. Legacy adjustment helpers remain available as
non-mutating discrepancy calculations; the calculation paths do not call them.
Self-leveling roller price adjustments and drywall/tile last-row balancing were
also removed. Preset totals no longer override actual displayed material sums.
Flooring copy/display now uses the actual computed threshold quantity rather
than substituting a `1–2` range for a priced quantity.

For each row: `reference_total = round(quantity * reference_price)` (whole KZT,
existing rounding convention). Materials total is the sum of displayed rows.
Grand total is materials + labor + explicitly disclosed additional amount.
Plumbing Business keeps the existing ₸150,000 package addition, separately
labeled **“Дополнительная сумма пакета (состав не указан)”**. It is not called a
material or labor cost. Persistence records it in `result_data.totals.additional_total`.
Existing saved estimates are not rewritten.

Variant selection updates the active title, summary count, total, rows, copy
source and all hidden save/request variant inputs. Server saves recalculate the
selected variant rather than trusting client amounts.

## Unresolved construction / business decisions

These remain assumptions in existing data, not validated construction norms:

1. **Ceiling Economy specification:** the existing coefficient changes quantities
   of Comfort rows while descriptions promise different materials. For the
   20 m² example it still contains comfort spotlights and a niche. Options:
   approve a real bill of materials per tier, or describe tiers as quantity
   scenarios. A preset budget cannot establish a negative niche or a discount.
2. **Preset target totals:** now disagree with corrected sums in several reference
   cases. Options: keep row sums as the estimate; separately label an approved
   budget target; or supply verified unit prices/discount rules. Do not silently
   force a material row to absorb a difference. Drywall/tile tier price ratios
   derived from existing target totals remain legacy assumptions.
3. **Plumbing ₸150,000 addition:** specify whether this is equipment, labor, a
   service fee, or should be removed. Until clarified it is an unclassified
   package addition, separately visible, not an invented line item.
4. **Geometric inference:** perimeter and wall area are inferred from floor area
   and room count rather than measured geometry. Options: retain as preliminary
   estimates with warnings, or collect actual dimensions/openings. Existing
   rounded-key reference lookups can create steps around neighboring areas;
   interpolation requires an approved rule, not an arbitrary software patch.
5. **Waste, packaging, electrical and heating design:** existing reserves,
   coefficients, fixture counts and system selections are not certified. Review
   real specifications with the responsible specialists before purchasing or
   construction. No coefficients or norms were introduced in this change.

## Reproducible verification

Environment: Python 3.12, Django 5.2.14 from the repository's pinned
`requirements.txt`; Node 24.22.1. Dependencies live in an isolated temporary venv.

```sh
python -m venv /tmp/eseptep-calculator-venv
/tmp/eseptep-calculator-venv/bin/pip install -r requirements.txt
/tmp/eseptep-calculator-venv/bin/python manage.py test -v 1
node --test calculators/js_tests/variants.test.cjs
git diff --check
```

Django: 12 test methods passed; temporary test database created/destroyed; system
check found no issues. Subtests cover all 12 defaults, inclusive minimum/maximum
inputs, every field's invalid numbers/choices, fractional counts, comma decimals,
missing inputs, invalid variants, no persistence on errors, valid authenticated
saves, all choices and area/reference neighbors with room/count variations,
row arithmetic, saved variants, the negative-niche reproduction and surcharge.
Package tests cover bounds, decimals, missing/invalid city/developer and area.
Node: 1 test passed covering both variant naming families and all three variants,
summary, total, visible panel, tab state, hidden inputs and clipboard selection.
`git diff --check`: no output (success).

Limitations: Node uses a small synthetic DOM to execute the shipped handlers;
this is not a full rendered-browser or accessibility audit. Calculated totals are
arithmetically consistent, not a certification of quantities or prices. No CI,
production, customer-data or project-upload verification is claimed.
