"""
Compliance Rule Libraries — pre-built, deterministic SOX/COSO/IFRS-adjacent
checks that plug into the same real-computation path as the AI Compliance
dialog's Rule Detection tab (services.ai_service.ComplianceReportGenerator.
compute_rule_violation), but skip the AI entirely on the way in.

Rule Detection today requires an AI provider to translate a free-text rule
into a filter condition before anything gets computed. These libraries ship
the condition already written, against logical field names (e.g. "amount",
"approver") that a mapping step resolves to a specific dataset's actual
column names — same idea as IFRS9Service.perform_staging's `mapping` dict.
That means every rule here runs with zero AI calls, zero API cost, and zero
dependency on an AI provider being configured at all.

Deliberately scoped to what compute_rule_violation can actually express:
a per-row filter (column vs. a literal/threshold, or a null check) or a
duplicate-record check. It cannot compare one column to another (e.g.
"Invoice Qty > GRN Qty") — that class of check already exists in the app
via the "Custom Column from Math" step (col('a') > col('b')) and doesn't
need a rule library; see the three-way-match Audit Program shipped
alongside this instead of a rule here.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# Rule Libraries
# =============================================================================

RULE_LIBRARIES: Dict[str, Dict[str, Any]] = {
    "sox_itgc_ap": {
        "display_name": "SOX — Accounts Payable & Procurement Controls",
        "framework": "SOX",
        "description": (
            "Authorization and completeness checks over a payment/invoice "
            "population, mapped to SOX 404 control activities."
        ),
        "rules": [
            {
                "id": "payment_without_approval",
                "name": "Payment Without Approval on File",
                "citation": "SOX 404 — Control Activities (Authorization)",
                "coso_component": "Control Activities",
                "severity": "high",
                "description": (
                    "Payments at or above the approval threshold must have an "
                    "approver recorded before disbursement."
                ),
                "recommendation": (
                    "Obtain evidence of approval for each flagged payment, or "
                    "correct the workflow so approval is captured before payment."
                ),
                "required_fields": {
                    "amount": "Numeric payment/invoice amount",
                    "approver": "Approver name or ID (blank = no approval on file)",
                },
                "optional_fields": {"reference": "Invoice/payment reference number (used as evidence)"},
                "params": {"threshold": {"label": "Approval threshold ($)", "default": 10000, "type": "number"}},
                "rule_type": "condition",
                "combine_operator": "AND",
                "conditions": [
                    {"field": "amount", "operator": ">=", "value_param": "threshold"},
                    {"field": "approver", "operator": "is_null"},
                ],
                "amount_field": "amount",
                "evidence_field": "reference",
            },
            {
                "id": "duplicate_vendor_payment",
                "name": "Duplicate Vendor Payment",
                "citation": "SOX 404 — Control Activities (Completeness/Accuracy)",
                "coso_component": "Control Activities",
                "severity": "high",
                "description": (
                    "The same vendor, amount, and invoice reference should not "
                    "appear more than once in the payment population."
                ),
                "recommendation": (
                    "Investigate each duplicate group for double payment; pursue "
                    "recovery from the vendor if a double payment is confirmed."
                ),
                "required_fields": {
                    "vendor": "Vendor name or ID",
                    "amount": "Payment amount",
                    "reference": "Invoice/reference number",
                },
                "rule_type": "duplicate_check",
                "duplicate_check_fields": ["vendor", "amount", "reference"],
                "amount_field": "amount",
                "evidence_field": "reference",
            },
            {
                "id": "split_purchase_proxy",
                "name": "Payment Just Below Approval Threshold",
                "citation": "SOX 404 — Control Activities (Authorization circumvention)",
                "coso_component": "Control Activities",
                "severity": "medium",
                "description": (
                    "Payments clustered just under the approval threshold can "
                    "indicate a purchase deliberately split to avoid a higher "
                    "approval level — this flags the population for follow-up, "
                    "it does not itself prove splitting occurred."
                ),
                "recommendation": (
                    "Review flagged payments for the same vendor/requester "
                    "occurring close together in time — the pattern, not any "
                    "single payment, is the actual evidence of splitting."
                ),
                "required_fields": {"amount": "Payment amount"},
                "optional_fields": {"reference": "Invoice/payment reference number (used as evidence)"},
                "params": {"threshold": {"label": "Approval threshold ($)", "default": 10000, "type": "number"}},
                "rule_type": "condition",
                "combine_operator": "AND",
                "conditions": [
                    {"field": "amount", "operator": ">=", "value_param": "threshold_low"},
                    {"field": "amount", "operator": "<", "value_param": "threshold"},
                ],
                "derived_params": {"threshold_low": ("threshold", 0.9)},
                "amount_field": "amount",
                "evidence_field": "reference",
            },
        ],
    },
    "coso_expense_travel": {
        "display_name": "COSO — Expense & Travel Control Activities",
        "framework": "COSO",
        "description": (
            "Documentation and policy-limit checks over an expense/travel "
            "population, mapped to COSO 2013 Control Activities."
        ),
        "rules": [
            {
                "id": "expense_without_receipt",
                "name": "Expense Without Receipt Reference",
                "citation": "COSO 2013 — Control Activities (Documentation)",
                "coso_component": "Control Activities",
                "severity": "medium",
                "description": (
                    "Expenses above the receipt threshold must have a receipt "
                    "reference on file."
                ),
                "recommendation": "Request the missing receipt or reject the claim per policy.",
                "required_fields": {
                    "amount": "Expense amount",
                    "receipt_reference": "Receipt/attachment reference (blank = no receipt on file)",
                },
                "params": {"threshold": {"label": "Receipt required above ($)", "default": 25, "type": "number"}},
                "rule_type": "condition",
                "combine_operator": "AND",
                "conditions": [
                    {"field": "amount", "operator": ">", "value_param": "threshold"},
                    {"field": "receipt_reference", "operator": "is_null"},
                ],
                "amount_field": "amount",
                "evidence_field": "receipt_reference",
            },
            {
                "id": "expense_over_policy_limit",
                "name": "Expense Over Policy Limit",
                "citation": "COSO 2013 — Control Activities (Policy compliance)",
                "coso_component": "Control Activities",
                "severity": "medium",
                "description": "Individual expense line items should not exceed the policy per-item limit.",
                "recommendation": "Confirm a documented exception was approved for each flagged item.",
                "required_fields": {"amount": "Expense amount"},
                "optional_fields": {"employee": "Employee name/ID (used as evidence)"},
                "params": {"limit": {"label": "Policy limit ($)", "default": 500, "type": "number"}},
                "rule_type": "condition",
                "combine_operator": "AND",
                "conditions": [{"field": "amount", "operator": ">", "value_param": "limit"}],
                "amount_field": "amount",
                "evidence_field": "employee",
            },
            {
                "id": "duplicate_expense_claim",
                "name": "Duplicate Expense Claim",
                "citation": "COSO 2013 — Control Activities (Completeness/Accuracy)",
                "coso_component": "Control Activities",
                "severity": "high",
                "description": "The same employee, amount, and date should not be claimed more than once.",
                "recommendation": "Investigate each duplicate group before reimbursement; recover if already paid twice.",
                "required_fields": {
                    "employee": "Employee name/ID",
                    "amount": "Expense amount",
                    "date": "Expense date",
                },
                "rule_type": "duplicate_check",
                "duplicate_check_fields": ["employee", "amount", "date"],
                "amount_field": "amount",
                "evidence_field": "employee",
            },
        ],
    },
    "period_end_je_risk": {
        "display_name": "Period-End Journal Entry Risk (IFRS/ISA 240-adjacent)",
        "framework": "IFRS",
        "description": (
            "Manual/topside journal entry checks relevant to IAS 1 fair "
            "presentation and ISA 240 fraud-risk procedures over the JE "
            "population. Not a substitute for the dedicated IFRS 9/15/16/36/37 "
            "estimate modules — this library only covers what a per-row filter "
            "can express."
        ),
        "rules": [
            {
                "id": "large_manual_entry",
                "name": "Large Manual/Topside Journal Entry",
                "citation": "ISA 240 — Risk of management override of controls",
                "coso_component": "Risk Assessment",
                "severity": "high",
                "description": "Manually posted entries above the threshold warrant substantive review.",
                "recommendation": "Obtain and inspect supporting documentation and business rationale for each entry.",
                "required_fields": {
                    "amount": "Journal entry amount",
                    "entry_type": "Entry type/source (e.g. 'Manual', 'System')",
                },
                "optional_fields": {"reference": "JE/document reference number (used as evidence)"},
                "params": {
                    "threshold": {"label": "Amount threshold ($)", "default": 50000, "type": "number"},
                    "manual_label": {"label": "Value identifying a manual entry", "default": "Manual", "type": "text"},
                },
                "rule_type": "condition",
                "combine_operator": "AND",
                "conditions": [
                    {"field": "amount", "operator": ">=", "value_param": "threshold"},
                    {"field": "entry_type", "operator": "==", "value_param": "manual_label"},
                ],
                "amount_field": "amount",
                "evidence_field": "reference",
            },
            {
                "id": "missing_je_description",
                "name": "Journal Entry Missing Description",
                "citation": "IAS 1 — Fair presentation / audit trail completeness",
                "coso_component": "Information & Communication",
                "severity": "low",
                "description": "Every journal entry should carry a text description supporting its business purpose.",
                "recommendation": "Require a description field before an entry can be posted.",
                "required_fields": {"description": "Journal entry text/description field"},
                "optional_fields": {"reference": "JE/document reference number (used as evidence)"},
                "rule_type": "condition",
                "combine_operator": "AND",
                "conditions": [{"field": "description", "operator": "is_null"}],
                "evidence_field": "reference",
            },
        ],
    },
}


def list_libraries() -> List[Dict[str, Any]]:
    """Return [{id, display_name, framework, description, rule_count}] for every library."""
    return [
        {
            "id": lib_id,
            "display_name": lib["display_name"],
            "framework": lib["framework"],
            "description": lib["description"],
            "rule_count": len(lib["rules"]),
        }
        for lib_id, lib in RULE_LIBRARIES.items()
    ]


def get_library(library_id: str) -> Dict[str, Any]:
    if library_id not in RULE_LIBRARIES:
        raise KeyError(f"Unknown rule library: {library_id}")
    return RULE_LIBRARIES[library_id]


def get_field_specs(library_id: str) -> Dict[str, Any]:
    """Union of every rule's required/optional fields and params in this
    library, for building a single mapping form that covers every rule at
    once. A rule whose required fields aren't all mapped is simply reported
    as not-computable later — it doesn't block the other rules."""
    library = get_library(library_id)
    required: Dict[str, str] = {}
    optional: Dict[str, str] = {}
    params: Dict[str, Dict[str, Any]] = {}
    for rule in library["rules"]:
        required.update(rule.get("required_fields", {}))
        optional.update(rule.get("optional_fields", {}))
        params.update(rule.get("params", {}))
    return {"required_fields": required, "optional_fields": optional, "params": params}


def suggest_mapping(df_columns: List[str], required_fields: Dict[str, str],
                     optional_fields: Dict[str, str]) -> Dict[str, str]:
    """Best-effort case-insensitive/substring auto-mapping from logical
    field name to an actual dataset column, same heuristic style already
    used by sox_dialog.py's user/action column auto-guess. Never guaranteed
    correct — always shown to the user to confirm/override before running."""
    lower_cols = {c.lower(): c for c in df_columns}
    mapping = {}
    for field_name in {**required_fields, **optional_fields}:
        if field_name in lower_cols:
            mapping[field_name] = lower_cols[field_name]
            continue
        match = next((c for c in df_columns if field_name.lower() in c.lower()), None)
        if match:
            mapping[field_name] = match
    return mapping


def _resolve_translation(rule: Dict[str, Any], mapping: Dict[str, str], params: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one rule + a field mapping + resolved params into the exact
    dict shape ComplianceReportGenerator.compute_rule_violation() expects -
    the same shape its AI-driven translate_rules_to_conditions() produces,
    just built here without any AI call."""
    required = rule.get("required_fields", {})
    missing = [f for f in required if not mapping.get(f)]
    if missing:
        return {
            "computable": False,
            "reason_if_not_computable": f"Not mapped to a column: {', '.join(missing)}",
        }

    resolved_params = dict(params or {})
    for derived_name, (base_param, factor) in rule.get("derived_params", {}).items():
        base_value = resolved_params.get(base_param)
        if base_value is not None:
            try:
                resolved_params[derived_name] = float(base_value) * factor
            except (TypeError, ValueError):
                pass

    amount_col = mapping.get(rule.get("amount_field") or "")
    evidence_col = mapping.get(rule.get("evidence_field") or "")

    if rule.get("rule_type") == "duplicate_check":
        cols = [mapping[f] for f in rule.get("duplicate_check_fields", []) if mapping.get(f)]
        if not cols:
            return {"computable": False, "reason_if_not_computable": "No mapped columns for duplicate check."}
        return {
            "computable": True,
            "rule_type": "duplicate_check",
            "duplicate_check_columns": cols,
            "amount_column": amount_col or None,
            "evidence_column": evidence_col or None,
        }

    conditions = []
    for cond in rule.get("conditions", []):
        column = mapping.get(cond["field"])
        if not column:
            continue
        entry = {"column": column, "operator": cond["operator"]}
        if "value_param" in cond:
            entry["value"] = resolved_params.get(cond["value_param"])
        else:
            entry["value"] = cond.get("value", "")
        conditions.append(entry)

    if not conditions:
        return {"computable": False, "reason_if_not_computable": "No mapped columns for this rule's conditions."}

    return {
        "computable": True,
        "rule_type": "condition",
        "conditions": conditions,
        "combine_operator": rule.get("combine_operator", "AND"),
        "amount_column": amount_col or None,
        "evidence_column": evidence_col or None,
    }


def apply_library(df, library_id: str, mapping: Dict[str, str],
                   params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Run every rule in a library against df, deterministically, with no
    AI call. Returns [{"rule": <rule dict>, "result": <compute_rule_violation
    dict>}] - the same result shape the AI Compliance dialog already knows
    how to render, just produced without asking an LLM to translate
    anything first.
    """
    from services.ai_service import ComplianceReportGenerator

    library = get_library(library_id)
    resolved_params = {}
    for name, spec in get_field_specs(library_id)["params"].items():
        resolved_params[name] = (params or {}).get(name, spec.get("default"))

    # compute_rule_violation() doesn't touch self.ai at all - it's pure
    # Polars/Python - so this runs with no AI provider configured.
    generator = ComplianceReportGenerator(ai_manager=None)

    results = []
    for rule in library["rules"]:
        translation = _resolve_translation(rule, mapping, resolved_params)
        if not translation.get("computable"):
            result = {
                "computable": False,
                "reason": translation.get("reason_if_not_computable", "Not computable."),
                "affected_count": 0, "total_count": len(df), "affected_pct": 0.0,
                "affected_amount": 0.0, "evidence": [], "matched_df": None, "mask": None,
            }
        else:
            result = generator.compute_rule_violation(df, translation)
        results.append({"rule": rule, "result": result})
    return results
