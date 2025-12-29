"""
Dialogs package for CAATmaster GUI
"""
from .pivot_dialog import PivotTableDialog
from .unpivot_dialog import UnpivotDialog, PowerPivotDialog
from .filter_dialog import FilterDialog
from .anomaly_dialog import AnomalyDetectionDialog
from .kmeans_dialog import KMeansDialog
from .benford_dialog import BenfordDialog
from .forecast_dialog import ForecastDialog
from .split_dialog import SplitColumnDialog
from .extract_dialog import ExtractDialog
from .standardize_dialog import StandardizeDialog

__all__ = [
    'PivotTableDialog',
    'PowerPivotDialog',
    'UnpivotDialog',
    'FilterDialog',
    'AnomalyDetectionDialog',
    'KMeansDialog',
    'BenfordDialog',
    'ForecastDialog',
    'SplitColumnDialog',
    'ExtractDialog',
    'StandardizeDialog',
]
