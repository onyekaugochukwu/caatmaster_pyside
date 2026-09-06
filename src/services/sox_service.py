"""
SOX Service for CAATmaster
Implements Sarbanes-Oxley (SOX) compliance tests: Segregation of Duties
(SoD) and IT General Controls (user access review).
"""
import polars as pl
from typing import Dict, List, Optional, Any, Tuple

class SoxService:
    """Service for SOX compliance analytics"""

    def analyze_sod_conflicts(
        self,
        df: pl.DataFrame,
        user_col: str,
        action_col: str,
        conflicts: List[Dict[str, Any]]
    ) -> pl.DataFrame:
        """
        Analyze Segregation of Duties (SoD) conflicts within a transaction log.

        Args:
            df: Input Transaction Log DataFrame
            user_col: Column containing User IDs
            action_col: Column containing Activity/Action names
            conflicts: List of conflict rules. Either the legacy pairwise form,
                       e.g. {"role_a": "Create Vendor", "role_b": "Pay Vendor"},
                       or an N-way toxic combination via "roles":
                       {"roles": ["Create Vendor", "Approve Invoice", "Process Payment"],
                        "severity": "Critical"} — flags a user only if they hold
                       EVERY role in the list, not just any two of them.

        Returns:
            DataFrame with new columns flagging conflicts:
            - sod_conflict_found (bool)
            - sod_conflict_detail (str)
        """
        if not user_col or not action_col or user_col not in df.columns or action_col not in df.columns:
            return df

        # Strategy:
        # 1. Group by User to get list of unique actions per user
        # 2. Identify Users who violate rules
        # 3. Join back to original transaction log to flag rows

        # Get unique actions per user
        user_actions = (
            df.lazy()
            .group_by(user_col)
            .agg(pl.col(action_col).unique().alias("actions_set"))
            .collect()
        )

        # Analyze conflicts
        violating_users = {} # UserID -> List of violation descriptions

        # Convert to python dict for faster iteration over rules
        # (Polars is fast, but looping over complex rules is easier in python for lists)
        user_map = dict(zip(user_actions[user_col], user_actions["actions_set"]))

        # Normalize each rule to a list of 2+ roles that must ALL be present -
        # accepts the legacy role_a/role_b pair alongside the newer "roles"
        # list so existing saved Audit Programs keep working unmodified.
        normalized_rules = []
        for rule in conflicts:
            roles = rule.get("roles")
            if not roles:
                roles = [rule.get("role_a"), rule.get("role_b")]
            roles = [str(r) for r in roles if r is not None]
            if len(roles) >= 2:
                normalized_rules.append({"roles": roles, "severity": rule.get("severity", "High")})

        for user, actions in user_map.items():
            # On some Polars versions, iterating a List-dtype column's
            # values (as this zip does) yields a Series per row rather
            # than a plain Python list - `if not actions` on a Series
            # raises ("truth value is ambiguous") instead of testing
            # emptiness, so normalize explicitly first.
            actions_list = actions.to_list() if hasattr(actions, "to_list") else list(actions or [])
            if not actions_list:
                continue

            user_violations = []
            actions_set = set(str(a) for a in actions_list if a is not None)

            for rule in normalized_rules:
                roles = rule["roles"]
                severity = rule["severity"]

                # Flag only if the user holds EVERY role in the combination,
                # not just any two of them - a 3+ role toxic combination
                # (e.g. "created vendor AND approved invoice AND processed
                # payment") is a materially different risk from any single
                # pair of those three, and shouldn't be under-reported as
                # one.
                if all(role in actions_set for role in roles):
                    user_violations.append(f"{severity}: {' + '.join(roles)}")

            if user_violations:
                violating_users[user] = "; ".join(user_violations)

        # Apply to original dataframe via native expressions rather than
        # map_elements (a per-row Python callback) - matters once this runs
        # against a multi-million-row transaction log, not just the small
        # per-user lookup table.
        return df.with_columns([
            pl.col(user_col).is_in(list(violating_users.keys())).alias("sod_conflict_found"),
            pl.col(user_col).replace_strict(violating_users, default=None).alias("sod_conflict_detail"),
        ])

    def access_review_analysis(
        self,
        df: pl.DataFrame,
        status_col: str,
        terminated_values: Optional[List[str]] = None,
        activity_date_col: Optional[str] = None,
        termination_date_col: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        Flag activity-log rows belonging to a terminated/inactive user -
        the classic SOX ITGC "user access review" test.

        Expects the activity log to already carry the user's status (and,
        optionally, their termination date) as columns - typically produced
        by joining an activity/transaction log to a user-master extract via
        the existing Join Datasets step before running this. This function
        only evaluates whatever status/dates are already present per row;
        it does not itself join two datasets.

        Args:
            df: Activity/transaction log, already joined to user status if
                a per-row flag from status alone isn't enough.
            status_col: Column holding the user's employment/account status.
            terminated_values: Status values that mean "should not have
                access" (case/whitespace-insensitive). Defaults to a common
                set: Terminated, Inactive, Disabled, Suspended.
            activity_date_col / termination_date_col: If both are present,
                also flags any activity recorded ON OR AFTER the user's
                termination date, regardless of what the status column says
                at the time this report is run (status may have since been
                corrected/cleared, but the activity still happened after
                termination).

        Returns:
            DataFrame with a new "access_review_flag" boolean column.
        """
        if status_col not in df.columns:
            return df

        terminated_values = terminated_values or ["Terminated", "Inactive", "Disabled", "Suspended"]
        normalized = [v.strip().lower() for v in terminated_values]

        flag_expr = (
            pl.col(status_col).cast(pl.Utf8).str.strip_chars().str.to_lowercase().is_in(normalized)
        )

        has_dates = (
            activity_date_col and termination_date_col
            and activity_date_col in df.columns and termination_date_col in df.columns
        )
        if has_dates:
            flag_expr = flag_expr | (
                pl.col(activity_date_col).is_not_null()
                & pl.col(termination_date_col).is_not_null()
                & (pl.col(activity_date_col) >= pl.col(termination_date_col))
            )

        return df.with_columns(flag_expr.fill_null(False).alias("access_review_flag"))
