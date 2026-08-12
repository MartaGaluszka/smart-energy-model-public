import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { RefresherCustomEvent, ViewWillEnter } from '@ionic/angular';
import { Chart, registerables } from 'chart.js';
import { Subscription } from 'rxjs';
import { ForecastValidationDailyRow, ForecastValidationHourlyRow } from '../services/api.service';
import { ForecastDataService, ForecastState } from '../services/forecast-data.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { MAX_FUTURE_DAYS } from '../services/forecast-data.service';

Chart.register(...registerables);

@Component({
  selector: 'app-tab3',
  templateUrl: 'tab3.page.html',
  styleUrls: ['tab3.page.scss'],
  standalone: false,
})
export class Tab3Page implements AfterViewInit, OnDestroy, ViewWillEnter {
  @ViewChild('forecastCanvas') private canvasRef?: ElementRef<HTMLCanvasElement>;

  state: ForecastState = {
    day: '',
    loading: true,
    hours: [],
    totalKwh: null,
    daily: [],
    hourlyValidation: [],
    note: null,
    error: null,
    canGoPrev: true,
    canGoNext: true,
    isComplete: true,
    actualSoFarKwh: null,
  };

  private chart?: Chart;
  private sub?: Subscription;
  /** Pierwsze wejście dostaje dane już pobrane przez konstruktor serwisu (singleton) —
   *  unikamy zbędnego podwójnego zapytania przy starcie apki. */
  private hasEnteredBefore = false;

  constructor(private readonly forecastData: ForecastDataService) {}

  ngAfterViewInit(): void {
    this.sub = this.forecastData.getState().subscribe((state) => {
      this.state = state;
      this.renderChart(state);
    });
  }

  /**
   * Ionic zachowuje taby "przy życiu" w tle — bez tego hooka dane pobrane raz przy starcie
   * apki (np. tylko poranny run 05:00) zostałyby na ekranie bezterminowo, mimo że w ciągu
   * dnia dochodzą kolejne runy (12:00/16:00) i nowe synchronizacje FoxESS. Odśwież przy
   * każdym powrocie na tę zakładkę, żeby dane uzupełniały się automatycznie.
   */
  ionViewWillEnter(): void {
    if (!this.hasEnteredBefore) {
      this.hasEnteredBefore = true;
      return;
    }
    this.forecastData.reload();
  }

  doRefresh(event: RefresherCustomEvent): void {
    this.forecastData.reload();
    // Stan ładowania (spinner na wykresie) i tak pojawi się przez `state.loading`;
    // zamykamy refresher od razu, żeby nie blokować gestu na czas requestu.
    setTimeout(() => event.target.complete(), 300);
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.chart?.destroy();
  }

  prevDay(): void {
    this.forecastData.shift(-1);
  }

  nextDay(): void {
    this.forecastData.shift(1);
  }

  goToday(): void {
    this.forecastData.goToday();
  }

  /** Znormalizowane YYYY-MM-DD (bez czasu). */
  private normalizedDay(dayIso: string | null | undefined): string {
    return (dayIso || '').slice(0, 10);
  }

  get selectedIsToday(): boolean {
    const day = this.normalizedDay(this.state.day);
    return !!day && day === todayIsoLocal();
  }

  get selectedIsFuture(): boolean {
    const day = this.normalizedDay(this.state.day);
    return !!day && day > todayIsoLocal();
  }

  /** Dziś / Jutro / Pojutrze + dd.mm — czytelna nawigacja outlook. */
  get dayNavLabel(): string {
    const formatted = this.formatDay(this.state.day);
    if (!formatted) return '…';
    const day = this.normalizedDay(this.state.day);
    const today = todayIsoLocal();
    if (day === today) return `Dziś · ${formatted}`;
    const jutro = shiftIsoDate(today, 1);
    const pojutrze = shiftIsoDate(today, MAX_FUTURE_DAYS);
    if (day === jutro) return `Jutro · ${formatted}`;
    if (day === pojutrze) return `Pojutrze · ${formatted}`;
    return formatted;
  }

  formatDay(dayIso: string): string {
    const d = this.normalizedDay(dayIso);
    if (!d) return '';
    const parts = d.split('-');
    if (parts.length < 3) return d;
    const [, month, day] = parts;
    return `${day}.${month}`;
  }

  /** Wiersze walidacji godzinowej pogrupowane per run_label (daily/midday/manual), posortowane po rank. */
  hourlyByLabel(): { label: string; rows: ForecastValidationHourlyRow[] }[] {
    const groups = new Map<string, ForecastValidationHourlyRow[]>();
    for (const row of this.state.hourlyValidation) {
      if (!groups.has(row.run_label)) groups.set(row.run_label, []);
      groups.get(row.run_label)!.push(row);
    }
    return Array.from(groups.entries()).map(([label, rows]) => ({
      label,
      rows: rows.slice().sort((a, b) => a.rank - b.rank),
    }));
  }

  runLabelName(label: string): string {
    const names: Record<string, string> = {
      daily: 'Poranna (05:00)',
      midday: 'Południowa (12:00)',
      manual: 'Ręczna',
      peak: 'Popołudniowa (16:00)',
    };
    return names[label] ?? label;
  }

  /** Kolor badge dla błędu DOBOWEGO (% względem sumy ~20–40 kWh — % ma sens). */
  errorClass(pct: number | null | undefined): string {
    if (pct === null || pct === undefined) return '';
    const abs = Math.abs(pct);
    if (abs <= 15) return 'se-error--ok';
    if (abs <= 35) return 'se-error--warn';
    return 'se-error--bad';
  }

  /**
   * Kolor dla błędu GODZINOWEGO — po |Δ| kWh, nie po %.
   * Przy małej rzeczywistości (np. 0,2 kWh o 6:00) % eksploduje (+920%) i kłamie wizualnie.
   */
  hourlyErrorClass(errKwh: number | null | undefined): string {
    if (errKwh === null || errKwh === undefined) return '';
    const abs = Math.abs(errKwh);
    if (abs <= 0.5) return 'se-error--ok';
    if (abs <= 1.2) return 'se-error--warn';
    return 'se-error--bad';
  }

  formatPct(pct: number | null | undefined): string {
    if (pct === null || pct === undefined) return '—';
    return `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`;
  }

  formatKwh(v: number | null | undefined): string {
    if (v === null || v === undefined) return '—';
    return `${v.toFixed(2)} kWh`;
  }

  /** Błąd godzinowy w kWh (prognoza − rzeczywistość); null gdy brak pomiaru. */
  hourlyErrorKwh(row: ForecastValidationHourlyRow): number | null {
    if (row.actual_pv_ml_kwh === null || row.actual_pv_ml_kwh === undefined) return null;
    if (row.error_vs_ml_kwh !== null && row.error_vs_ml_kwh !== undefined) {
      return row.error_vs_ml_kwh;
    }
    return row.predicted_kwh - row.actual_pv_ml_kwh;
  }

  formatHourlyError(row: ForecastValidationHourlyRow): string {
    const err = this.hourlyErrorKwh(row);
    if (err === null) return '—';
    const sign = err > 0 ? '+' : '';
    return `${sign}${err.toFixed(2)} kWh`;
  }

  trackByLabel(_i: number, item: { label: string }): string {
    return item.label;
  }

  trackByRank(_i: number, item: ForecastValidationHourlyRow): string {
    return `${item.run_label}-${item.rank}`;
  }

  trackByRunLabel(_i: number, item: ForecastValidationDailyRow): string {
    return item.run_label;
  }

  private renderChart(state: ForecastState): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;

    const labels = state.hours.map((h) => `${h.hour}:00`);
    const predicted = state.hours.map((h) => h.predictedKwh);
    const actual = state.hours.map((h) => h.actualKwh);
    // Błąd w kWh (nie %): przy actual≈0 % eksploduje (np. 2.0 vs 0.2 = +920%)
    // i rozciąga oś do 1000%, ukrywając realny obraz reszty dnia (~±1–2 kWh).
    const errorKwh = state.hours.map((h) =>
      h.actualKwh === null || h.actualKwh === undefined ? null : h.predictedKwh - h.actualKwh,
    );

    // Zawsze odtwarzaj wykres — zmieniały się osie/etykiety (z % na kWh).
    this.chart?.destroy();
    this.chart = undefined;

    this.chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Prognoza (kWh)',
            data: predicted,
            borderColor: '#E6A012',
            backgroundColor: 'rgba(230, 160, 18, 0.15)',
            pointRadius: 2,
            tension: 0.35,
            fill: true,
            yAxisID: 'y',
          },
          {
            label: 'Rzeczywistość (kWh)',
            data: actual,
            borderColor: '#3D8B5F',
            backgroundColor: 'rgba(61, 139, 95, 0.1)',
            pointRadius: 2,
            tension: 0.35,
            fill: false,
            spanGaps: false,
            yAxisID: 'y',
          },
          {
            label: 'Błąd (kWh)',
            data: errorKwh,
            borderColor: '#B23B3B',
            backgroundColor: 'rgba(178, 59, 59, 0.08)',
            borderDash: [4, 3],
            pointRadius: 1,
            tension: 0.2,
            fill: false,
            spanGaps: false,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: state.hours.some((h) => h.actualKwh !== null && h.actualKwh !== undefined)
              ? 'Prognoza PV vs rzeczywistość — godzinowo'
              : 'Prognoza PV — outlook godzinowy',
            color: '#2B2E33',
            font: { size: 13, weight: 'bold' },
            padding: { bottom: 8 },
          },
          legend: {
            display: true,
            position: 'bottom',
            labels: { color: '#5C636A', font: { size: 11 }, boxWidth: 12, padding: 12 },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#5C636A', font: { size: 10 } },
            title: { display: true, text: 'Godzina', color: '#5C636A', font: { size: 11 } },
          },
          y: {
            type: 'linear',
            position: 'left',
            beginAtZero: true,
            grid: { color: '#E3DFD6' },
            ticks: { color: '#5C636A', font: { size: 10 } },
            title: { display: true, text: 'Energia (kWh)', color: '#5C636A', font: { size: 11 } },
          },
          y1: {
            type: 'linear',
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#B23B3B', font: { size: 10 }, callback: (v) => `${v} kWh` },
            title: {
              display: true,
              text: 'Błąd (kWh) = prognoza − rzeczywistość',
              color: '#B23B3B',
              font: { size: 10 },
            },
          },
        },
      },
    });
  }
}
