"""Smart Energy Model - Financial module"""
from .prosumer_deposit import (
    DepositSummary,
    DepositSummaryRCEm,
    calculate_cumulative_deposit,
    calculate_cumulative_deposit_rcem,
    calculate_prosumer_deposit,
    calculate_prosumer_deposit_rcem,
)
from .roi_calculator import FinancialAnalyzer

__all__ = [
    'FinancialAnalyzer',
    'DepositSummary',
    'DepositSummaryRCEm',
    'calculate_prosumer_deposit',
    'calculate_prosumer_deposit_rcem',
    'calculate_cumulative_deposit',
    'calculate_cumulative_deposit_rcem',
]
