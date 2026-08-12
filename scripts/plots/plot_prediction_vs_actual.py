"""
Wykres: Prognoza vs Rzeczywiste PV — deleguje do plot_pv_timeseries_comparison.py
"""

from scripts.plot_pv_timeseries_comparison import build_chart

if __name__ == '__main__':
    build_chart(show=False)
