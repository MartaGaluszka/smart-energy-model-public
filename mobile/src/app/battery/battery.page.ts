import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { Chart, ChartDataset, Plugin, registerables } from 'chart.js';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  ApiService,
  BatteryPlanHour,
  BatterySettingsResponse,
  BatterySettingsUpdate,
  ShadowSavingsResponse,
} from '../services/api.service';
import { todayIsoLocal } from '../utils/date-utils';

Chart.register(...registerables);

type SeasonMode = 'auto' | 'summer' | 'autumn' | 'spring' | 'winter';

interface ShadowPeriodRow {
  key: 'day' | 'month' | 'ytd';
  label: string;
  loading: boolean;
  error: boolean;
  data: ShadowSavingsResponse | null;
}

@Component({
  selector: 'app-battery',
  templateUrl: './battery.page.html',
  styleUrls: ['./battery.page.scss'],
  standalone: false,
})
export class BatteryPage implements AfterViewInit, OnDestroy, ViewWillEnter {
  @ViewChild('planCanvas') private canvasRef?: ElementRef<HTMLCanvasElement>;

  loading = true;
  saving = false;
  error: string | null = null;
  saveMessage: string | null = null;

  season: SeasonMode = 'auto';
  seasonResolved = '';
  socMinPercent = 20;
  socReservePercent = 20;
  socTargetPercent = 80;
  efficiencyPct = 93;
  capacityKwh: number | null = 10.36;

  planDate = todayIsoLocal();
  planSeason = '';
  planNote = '';
  planHours: BatteryPlanHour[] = [];
  pvByHour: (number | null)[] = [];

  shadowRows: ShadowPeriodRow[] = [];
  shadowMethodNote = '';

  private chart?: Chart;
  private viewReady = false;

  readonly seasonOptions: { value: SeasonMode; label: string }[] = [
    { value: 'auto', label: 'Auto' },
    { value: 'summer', label: 'Lato' },
    { value: 'autumn', label: 'Jesień' },
    { value: 'winter', label: 'Zima' },
    { value: 'spring', label: 'Wiosna' },
  ];

  /** Zalecane rezerwy = backend BAT.5 / B1 (nie mylić z dnem FoxESS ~10%). */
  private readonly recommendedReserve: Record<Exclude<SeasonMode, 'auto'>, number> = {
    summer: 20,
    autumn: 22,
    winter: 40,
    spring: 20,
  };

  constructor(private readonly api: ApiService) {}

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.renderChart();
  }

  ionViewWillEnter(): void {
    this.reload();
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
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

  formatPln(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return `${value.toFixed(2).replace('.', ',')} zł`;
  }

  onSeasonChange(value: string | number | undefined): void {
    if (typeof value !== 'string') return;
    if (!['auto', 'summer', 'autumn', 'spring', 'winter'].includes(value)) return;
    this.season = value as SeasonMode;
    this.applyRecommendedReserveForSeason();
  }

  /** Podgląd zalecanej rezerwy przy przełączaniu sezonu (przed Zapisz). */
  private applyRecommendedReserveForSeason(): void {
    if (this.season === 'auto') {
      const resolved = (this.seasonResolved || 'summer') as Exclude<SeasonMode, 'auto'>;
      const rec = this.recommendedReserve[resolved] ?? 20;
      this.socReservePercent = rec;
      this.socMinPercent = rec;
      return;
    }
    const rec = this.recommendedReserve[this.season];
    this.socReservePercent = rec;
    this.socMinPercent = rec;
  }

  saveSettings(): void {
    this.saving = true;
    this.saveMessage = null;
    this.error = null;
    const body: BatterySettingsUpdate = {
      soc_min_percent: this.socMinPercent,
      soc_target_percent: this.socTargetPercent,
      efficiency_pct: this.efficiencyPct,
      price_zone1: null,
      price_zone2: null,
      season: this.season,
      battery_capacity_kwh: this.capacityKwh,
      ac_power_kw: null,
    };
    this.api.updateBatterySettings(body).subscribe({
      next: (row) => {
        this.applySettings(row);
        this.saving = false;
        this.saveMessage = 'Zapisano ustawienia.';
        this.reloadPlan();
      },
      error: () => {
        this.saving = false;
        this.error = 'Nie udało się zapisać ustawień baterii.';
      },
    });
  }

  reload(): void {
    this.loading = true;
    this.error = null;
    this.api.getBatterySettings().subscribe({
      next: (row) => {
        this.applySettings(row);
        this.loading = false;
        this.reloadPlan();
        this.reloadShadow();
      },
      error: () => {
        this.loading = false;
        this.error = 'Nie udało się pobrać ustawień baterii.';
        this.reloadShadow();
      },
    });
  }

  private applySettings(row: BatterySettingsResponse): void {
    this.season = (row.season as SeasonMode) || 'auto';
    this.seasonResolved = row.season_resolved;
    this.socMinPercent = row.soc_min_percent;
    this.socReservePercent = row.soc_reserve_percent;
    this.socTargetPercent = row.soc_target_percent;
    this.efficiencyPct = row.efficiency_pct;
    this.capacityKwh = row.battery_capacity_kwh;
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
          // trigger change detection for array mutation
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
        setTimeout(() => this.renderChart());
      },
      error: () => {
        this.planHours = [];
        this.pvByHour = [];
        this.error = this.error ?? 'Nie udało się pobrać planu 24h.';
      },
    });
  }

  private renderChart(): void {
    if (!this.viewReady) return;
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas || !this.planHours.length) return;

    const labels = this.planHours.map((h) => `${h.hour}:00`);
    const soc = this.planHours.map((h) => h.planned_soc_percent);
    const pv = this.pvByHour.map((v) => v);
    const cheapMask = this.planHours.map((h) => (h.zone === 2 ? 100 : null));
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
      {
        type: 'line',
        label: 'Tania G12w',
        data: cheapMask,
        borderColor: 'rgba(79, 111, 82, 0.0)',
        backgroundColor: 'rgba(79, 111, 82, 0.0)',
        pointRadius: 0,
        fill: false,
        yAxisID: 'y',
        order: 2,
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
          legend: {
            position: 'bottom',
            labels: { boxWidth: 12, font: { size: 11 } },
          },
          tooltip: {
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
