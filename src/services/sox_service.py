"""
SOX Service for CAATmaster
Implements Sarbanes-Oxley (SOX) compliance tests, specifically Segregation of Duties (SoD).
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
        conflicts: List[Dict[str, str]]
    ) -> pl.DataFrame:
        """
        Analyze Segregation of Duties (SoD) conflicts within a transaction log.
        
        Args:
            df: Input Transaction Log DataFrame
            user_col: Column containing User IDs
            action_col: Column containing Activity/Action names
            conflicts: List of conflict rules, e.g., [{"role_a": "Create Vendor", "role_b": "Pay Vendor"}]
            
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
        
        for user, actions in user_map.items():
            if not actions: continue
            
            user_violations = []
            actions_set = set(str(a) for a in actions if a is not None)
            
            for rule in conflicts:
                a = str(rule.get("role_a"))
                b = str(rule.get("role_b"))
                severity = rule.get("severity", "High")
                
                # Check if user has both A and B
                # Note: This is a simplified exact match. In real world, might need regex or "starts with"
                has_a = a in actions_set
                has_b = b in actions_set
                
                if has_a and has_b:
                    user_violations.append(f"{severity}: {a} + {b}")
            
            if user_violations:
                violating_users[user] = "; ".join(user_violations)
        
        # Create result columns based on map
        
        def get_conflict_flag(user_val):
            return user_val in violating_users
            
        def get_conflict_desc(user_val):
            return violating_users.get(user_val, None)
            
        # Apply to original dataframe
        return df.with_columns([
            pl.col(user_col).map_elements(get_conflict_flag, return_dtype=pl.Boolean).alias("sod_conflict_found"),
            pl.col(user_col).map_elements(get_conflict_desc, return_dtype=pl.Utf8).alias("sod_conflict_detail")
        ])
