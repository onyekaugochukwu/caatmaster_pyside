# AI Feature Test Kit

Files here:
- `transactions.csv` — 30 vendor payment transactions, with deliberately-baked-in issues (see "Ground truth" below).
- `compliance_policy.txt` — a free-text policy document for the Compliance Report dialog's **Policy Check** tab.
- `detection_rules.txt` — pipe-delimited rules for the **Violation Detection** tab (paste directly into the rules box).

## How to load

Upload/open `transactions.csv` as a dataset in CaatMaster (File → Import, or drag it into the sidebar).

## Ground truth (computed directly from the CSV — use this to check the AI's numbers)

| Rule | Real count | Real dollar impact | Real matching IDs |
|---|---|---|---|
| `amount > 1000 AND approver is null` | **12** of 30 (40%) | **$69,800.00** | TXN-1002 (×2, see duplicate below), 1007, 1009, 1012, 1017, 1019, 1022, 1025, 1027, 1028, 1030 |
| `category is null` | **3** | — | TXN-1009, 1015, 1025 |
| `amount > 10000` | **1** | $45,250.00 | TXN-1009 |
| Exact full-row duplicates | **1** | — | TXN-1002 / TXN-1008 are byte-for-byte identical |

When you run **Statistics → AI → AI Analyze Dataset** or the Compliance Report dialog against this file, the affected counts/amounts/evidence it shows should match this table exactly — they're computed from the complete 30-row file, not estimated. If a number doesn't match, something regressed.

## Things to try

**AI menu operations** (Transform pipeline, on the `notes` column):
- **AI Sentiment** — TXN-1012/1028 read positive, TXN-1017/1022 read negative/frustrated, most others are neutral.
- **AI Summarize** — condenses the longer notes.
- **AI Extract** (entity_type=email or phone) — none of the notes contain either, so extraction should correctly come back empty rather than inventing one.
- **AI Classify** — try categories `["Positive Experience", "Negative Experience", "Routine/Neutral"]`.
- **AI Pattern Learning** — instruction: "extract just the vendor concern, if any, otherwise empty string".

**AI Analyze Dataset** (Statistics or AI panel quick action): should report the real duplicate count, real null rates per column, and the $45,250 outlier on `amount` — check its data quality score and audit insights against the table above.

**Compliance Report dialog**:
- *Policy Check* tab: paste in `compliance_policy.txt`. Expect findings for rules 1, 2, 3, and 4 above, each with the real counts from the table.
- *Violation Detection* tab: paste in `detection_rules.txt`. Same expected numbers.
- *Draft Report* tab: type a few findings manually and generate a draft — this one's always been safe (it only drafts prose around what you type), nothing to verify against ground truth here.

Check **AI menu → AI Activity Log...** afterward — every real call's prompt and response should be there, so you can see exactly what was sent and what came back for any of the above.
