import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { Chart, ChartDataset, Plugin, registerables } from 'chart.js';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  ApiService,
  AcRuntimeResponse,
  BatteryPlanHour,
  BatterySuggestionResponse,
  ShadowSavingsResponse,
} from '../../services/api.service';
import { BatteryStateService } from '../services/battery-state.service';
import { todayIsoLocal } from '../../utils/date-utils';

Chart.register(...registerables);

interface ShadowPeriodRow {
  key: 'day' | 'month' | 'ytd';
  label: string;
  loading: boolean;
  error: boolean;
  data: ShadowSavingsResponse | null;
}

@Component({
  selector: 'app-battery-analytics',
  templateUrl: './battery-analytics.page.html',
  styleUrls: ['../battery-shared.scss'],
  standalone: false,
})
export class BatteryAnalyticsPage implements AfterViewInit, OnDestroy, ViewWillEnter {
  @ViewChild('planCanvas') private canvasRef?: ElementRef<HTMLCanvasElement>;

  loading = true;
  error: string | null = null;

  suggestion: BatterySuggestionResponse | null = null;
  shadowRows: ShadowPeriodRow[] = [];
  shadowMethodNote = '';

  planDate = todayIsoLocal();
  planSeason = '';
  planNote = '';
  planHours: BatteryPlanHour[] = [];
  pvByHour: (number | null)[] = [];

  /** T4.28a — interaktywny kalkulator AC */
  isAcCalculated = false;
  acPowerKw = 1.2;
  calculatedHours = 0;
  calculatedMinutes = 0;
  suggestedTurnOffTime: string | null = null;
  acRuntimeNote = '';
  acSocNow: number | null = null;
  acNightLoadKw: number | null = null;
  acLoading = false;
  acCalcError: string | null = null;

  private chart?: Chart;
  private viewReady = false;
  private acPersistTimer?: ReturnType<typeof setTimeout>;

  constructor(
    private readonly api: ApiService,
    readonly stateService: BatteryStateService,
  ) {}

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.scheduleRenderChart();
  }

  ionViewWillEnter(): void {
    this.isAcCalculated = false;
    this.acCalcError = null;
    this.syncAcPowerFromState();
    this.reloadAll();
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
    clearTimeout(this.acPersistTimer);
  }

  /** Moc AC z BatteryStateService (Single Source of Truth). */
  get acPower(): number {
    return this.stateService.state()?.ac_power_kw ?? this.acPowerKw;
  }

  formatPln(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return `${value.toFixed(2).replace('.', ',')} zł`;
  }

  seasonLabel(season: string): string {
    const map: Record<string, string> = {
      summer: 'lato',
      autumn: 'jesień',
      spring: 'wiosna',
      winter: 'zima',
      auto: 'auto',
    };
    return map[season] ?? season;
  }

  calculateAcLimit(): void {
    this.acLoading = true;
    this.acCalcError = null;
    this.syncAcPowerFromState();
    this.api.postAcRuntime(this.acPowerKw).subscribe({
      next: (row) => {
        this.applyAcResult(row);
        this.isAcCalculated = true;
        this.acLoading = false;
      },
      error: () => {
        this.acLoading = false;
        this.acCalcError = 'Nie udało się obliczyć limitu czasu.';
      },
    });
  }

  /** Zwiń widget — powrót do stanu „Oblicz limit czasu”. */
  closeAcWidget(): void {
    this.isAcCalculated = false;
    this.acCalcError = null;
  }

  onAcPowerInput(event: Event): void {
    if (!this.isAcCalculated) return;
    const value = Number((event.target as HTMLInputElement).value);
    if (Number.isNaN(value)) return;
    this.acPowerKw = value;
    clearTimeout(this.acPersistTimer);
    this.acPersistTimer = setTimeout(() => {
      this.stateService.persistAcPowerKw(value, { silent: true }).subscribe();
      this.calculateAcLimit();
    }, 400);
  }

  private syncAcPowerFromState(): void {
    const kw = this.stateService.state()?.ac_power_kw;
    if (kw != null && kw > 0) {
      this.acPowerKw = kw;
    }
  }

  private applyAcResult(row: AcRuntimeResponse): void {
    this.acPowerKw = row.ac_power_kw;
    const totalHours = Math.max(0, row.hours_safe);
    this.calculatedHours = Math.floor(totalHours);
    this.calculatedMinutes = Math.round((totalHours - this.calculatedHours) * 60);
    this.suggestedTurnOffTime = row.suggested_off_at;
    this.acRuntimeNote = row.note;
    this.acSocNow = row.soc_now_percent;
    this.acNightLoadKw = row.night_load_kw;
  }

  private reloadAll(): void {
    this.loading = true;
    this.error = null;
    this.syncAcPowerFromState();
    this.reloadShadow();
    this.reloadSuggestion();
    this.reloadPlan();
  }

  private reloadSuggestion(): void {
    this.api.getBatterySuggestion().subscribe({
      next: (row) => {
        this.suggestion = row;
        this.loading = false;
      },
      error: () => {
        this.suggestion = null;
        this.loading = false;
      },
    });
  }

  private periodBounds(): { key: 'day' | 'month' | 'ytd'; label: string; from: string; to: string }[] {
    const to = todayIsoLocal();
    const [y, m] = to.split('-');
    const monthStart = `${y}-${m}-01`;
    const ytdStart = `${y}-01-01`;
    return [
      { key: 'day', label: 'Dziś', from: to, to },
      { key: 'month', label: 'Ten miesiąc', from: monthStart, to },
      { key: 'ytd', label: 'Od początku roku', from: ytdStart, to },
    ];
  }

  private reloadShadow(): void {
    const periods = this.periodBounds();
    this.shadowRows = periods.map((p) => ({
      key: p.key,
      label: p.label,
      loading: true,
      error: false,
      data: null,
    }));
    this.shadowMethodNote = '';

    periods.forEach((p, idx) => {
      this.api.getShadowSavings(p.from, p.to).subscribe({
        next: (data) => {
          this.shadowRows[idx] = {
            key: p.key,
            label: p.label,
            loading: false,
            error: false,
            data,
          };
          if (data.method_note) this.shadowMethodNote = data.method_note;
          this.shadowRows = [...this.shadowRows];
        },
        error: () => {
          this.shadowRows[idx] = {
            key: p.key,
            label: p.label,
            loading: false,
            error: true,
            data: null,
          };
          this.shadowRows = [...this.shadowRows];
        },
      });
    });
  }

  private reloadPlan(): void {
    const day = todayIsoLocal();
    this.planDate = day;
    forkJoin({
      plan: this.api.getBatteryPlan(day),
      pv: this.api.getForecastHourly(day).pipe(catchError(() => of(null))),
    }).subscribe({
      next: ({ plan, pv }) => {
        this.planHours = plan.hours ?? [];
        this.planSeason = plan.season;
        this.planNote = plan.note || 'Plan doradczy — brak wysyłki komend do falownika.';
        const map = new Map<number, number>();
        for (const h of pv?.hours ?? []) {
          map.set(h.hour, h.predicted_kwh);
        }
        this.pvByHour = Array.from({ length: 24 }, (_, hour) => map.get(hour) ?? null);
        this.scheduleRenderChart();
      },
      error: () => {
        this.planHours = [];
        this.pvByHour = [];
        this.error = this.error ?? 'Nie udało się pobrać planu 24h.';
      },
    });
  }

  private scheduleRenderChart(attempt = 0): void {
    const canvas = this.canvasRef?.nativeElement;
    if (canvas && this.planHours.length) {
      this.renderChart();
      return;
    }
    if (attempt >= 20) return;
    setTimeout(() => this.scheduleRenderChart(attempt + 1), 50);
  }

  private renderChart(): void {
    if (!this.viewReady) return;
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas || !this.planHours.length) return;

    const labels = this.planHours.map((h) => `${h.hour}:00`);
    const soc = this.planHours.map((h) => h.planned_soc_percent);
    const pv = this.pvByHour.map((v) => v);
    const zones = this.planHours.map((h) => h.zone);

    this.chart?.destroy();

    const cheapBands: Plugin = {
      id: 'cheapBands',
      beforeDraw: (chart) => {
        const yScale = chart.scales['y'];
        const xScale = chart.scales['x'];
        if (!yScale || !xScale) return;
        const ctx = chart.ctx;
        ctx.save();
        for (let i = 0; i < zones.length; i++) {
          if (zones[i] !== 2) continue;
          const x0 = xScale.getPixelForValue(i);
          const x1 = xScale.getPixelForValue(Math.min(i + 1, zones.length - 1));
          const width = i === zones.length - 1 ? Math.max(8, (x1 - x0) * 0.5) : x1 - x0;
          ctx.fillStyle = 'rgba(79, 111, 82, 0.10)';
          ctx.fillRect(x0, yScale.top, width, yScale.bottom - yScale.top);
        }
        ctx.restore();
      },
    };

    const datasets: ChartDataset[] = [
      {
        type: 'bar',
        label: 'PV prognoza (kWh)',
        data: pv,
        backgroundColor: 'rgba(230, 160, 18, 0.35)',
        borderColor: '#E6A012',
        borderWidth: 1,
        yAxisID: 'y1',
        order: 3,
      },
      {
        type: 'line',
        label: 'SoC plan (%)',
        data: soc,
        borderColor: '#3D4450',
        backgroundColor: 'rgba(61, 68, 80, 0.08)',
        pointRadius: 2,
        tension: 0.25,
        fill: false,
        yAxisID: 'y',
        order: 1,
      },
    ];

    this.chart = new Chart(canvas, {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
            callbacks: {
              afterBody: (items) => {
                const idx = items[0]?.dataIndex ?? 0;
                const hour = this.planHours[idx];
                if (!hour) return [];
                const bits = [`Strefa: ${hour.zone_label}`];
                if (hour.force_charge_recommended) bits.push('Sugestia: ForceCharge');
                return bits;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } },
            grid: { display: false },
          },
          y: {
            position: 'left',
            min: 0,
            max: 100,
            title: { display: true, text: 'SoC %', font: { size: 11 } },
            ticks: { font: { size: 10 } },
          },
          y1: {
            position: 'right',
            min: 0,
            title: { display: true, text: 'PV kWh', font: { size: 11 } },
            grid: { drawOnChartArea: false },
            ticks: { font: { size: 10 } },
          },
        },
      },
      plugins: [cheapBands],
    });
  }
}
