import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { Chart, ChartDataset, Plugin, registerables } from 'chart.js';
import { BehaviorSubject, Observable, Subscription, forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  ApiService,
  AcRuntimeResponse,
  BatteryPlanHour,
  BatterySuggestionResponse,
} from '../services/api.service';
import { HomeDataService, HomeKpi, SyncStatus, Suggestion } from '../services/home-data.service';
import { BatteryStateService } from '../battery/services/battery-state.service';
import { todayIsoLocal } from '../utils/date-utils';

Chart.register(...registerables);

@Component({
  selector: 'app-tab1',
  templateUrl: 'tab1.page.html',
  styleUrls: ['tab1.page.scss'],
  standalone: false,
})
export class Tab1Page implements OnInit, AfterViewInit, OnDestroy, ViewWillEnter {
  @ViewChild('planCanvas') private canvasRef?: ElementRef<HTMLCanvasElement>;

  kpi$!: Observable<HomeKpi | null>;
  sync$!: Observable<SyncStatus>;
  suggestions$!: Observable<Suggestion[]>;
  battery$!: Observable<BatterySuggestionResponse | null>;
  /** BAT.5: próg koloru SoC = rezerwa sezonowa (lato 20 / zima 40). */
  socReserve = 20;
  /** T4.16: skrót shadow miesiąc (pełna karta na /tabs/battery). */
  shadowMonthPln: number | null = null;
  shadowLoading = false;
  acRuntime: AcRuntimeResponse | null = null;
  acPowerKw = 1.2;
  planHours: BatteryPlanHour[] = [];
  private pvByHour: (number | null)[] = [];
  private chart?: Chart;
  private viewReady = false;
  private acSub?: Subscription;
  private acPreviewTimer?: ReturnType<typeof setTimeout>;
  private acPersistTimer?: ReturnType<typeof setTimeout>;
  private batterySub?: Subscription;
  private shadowSub?: Subscription;
  private suggestionsSub?: Subscription;
  private planSub?: Subscription;
  private readonly suggestionsSubject = new BehaviorSubject<Suggestion[]>([]);

  constructor(
    readonly homeData: HomeDataService,
    private readonly api: ApiService,
    private readonly batteryState: BatteryStateService,
  ) {}

  ngOnInit() {
    this.kpi$ = this.homeData.getKpi();
    this.sync$ = this.homeData.getSyncStatus();
    this.suggestions$ = this.suggestionsSubject.asObservable();
    this.battery$ = this.homeData.getBatterySuggestion();
    this.batterySub = this.battery$.subscribe((row) => {
      this.socReserve = row?.soc_reserve_percent ?? 20;
    });
    this.reloadSuggestions();
  }

  ngAfterViewInit(): void {
    this.viewReady = true;
    this.renderChart();
  }

  ngOnDestroy() {
    this.batterySub?.unsubscribe();
    this.shadowSub?.unsubscribe();
    this.suggestionsSub?.unsubscribe();
    this.acSub?.unsubscribe();
    this.planSub?.unsubscribe();
    clearTimeout(this.acPreviewTimer);
    clearTimeout(this.acPersistTimer);
    this.chart?.destroy();
  }

  ionViewWillEnter() {
    this.homeData.refreshAll();
    this.reloadShadowMonth();
    this.reloadSuggestions();
    this.reloadAc();
    this.reloadPlanChart();
  }

  formatSavingsNumber(value: number | null): string {
    if (value === null || Number.isNaN(value)) return '—';
    return value.toFixed(2).replace('.', ',');
  }

  onAcPowerInput(event: Event): void {
    const value = Number((event.target as HTMLInputElement).value);
    if (Number.isNaN(value) || !this.acRuntime) return;
    this.acPowerKw = value;
    clearTimeout(this.acPreviewTimer);
    this.acPreviewTimer = setTimeout(() => this.previewAcRuntime(value), 150);
    clearTimeout(this.acPersistTimer);
    this.acPersistTimer = setTimeout(() => this.persistAcPower(value), 600);
  }

  formatSoc(value: number | null): string {
    if (value === null || Number.isNaN(value)) return '—';
    return String(Math.round(value));
  }

  planModeAdjective(season: string): string {
    const map: Record<string, string> = {
      summer: 'LETNI',
      autumn: 'JESIENNY',
      winter: 'ZIMOWY',
      spring: 'WIOSENNY',
    };
    return map[season] ?? season.toUpperCase();
  }

  planGoal(bat: BatterySuggestionResponse): string {
    if (!bat.force_charge_night_recommended && !bat.force_charge_afternoon_recommended) {
      return 'Wystarczy PV. Dziś bez ładowania z sieci.';
    }
    return bat.charge_when_summary || 'Doładuj w taniej G12w.';
  }

  planG12w(bat: BatterySuggestionResponse): string {
    if (!bat.force_charge_night_recommended && !bat.force_charge_afternoon_recommended) {
      return 'Pomiń (noc i popołudnie)';
    }
    const night = bat.force_charge_night_recommended
      ? bat.force_charge_night_label || 'noc'
      : 'Pomiń';
    const afternoon = bat.force_charge_afternoon_recommended
      ? bat.force_charge_afternoon_label || 'popołudnie'
      : 'Pomiń';
    return `Noc: ${night}; popołudnie: ${afternoon}`;
  }

  private reloadShadowMonth(): void {
    const to = todayIsoLocal();
    const [y, m] = to.split('-');
    const from = `${y}-${m}-01`;
    this.shadowLoading = true;
    this.shadowSub?.unsubscribe();
    this.shadowSub = this.api.getShadowSavings(from, to).subscribe({
      next: (row) => {
        this.shadowMonthPln = row.shadow_savings_pln;
        this.shadowLoading = false;
      },
      error: () => {
        this.shadowMonthPln = null;
        this.shadowLoading = false;
      },
    });
  }

  private reloadAc(): void {
    this.batteryState.loadSettings();
    this.acSub?.unsubscribe();
    this.acSub = this.api.getAcRuntime().subscribe({
      next: (row) => {
        if (row.show_card) {
          this.acRuntime = row;
          this.acPowerKw = row.ac_power_kw;
        } else {
          this.acRuntime = null;
        }
      },
      error: () => {
        this.acRuntime = null;
      },
    });
  }

  private previewAcRuntime(kw: number): void {
    if (!this.acRuntime) return;
    this.api.postAcRuntime(kw).subscribe({
      next: (row) => {
        this.acRuntime = { ...row, show_card: true };
        this.acPowerKw = row.ac_power_kw;
      },
    });
  }

  private persistAcPower(kw: number): void {
    this.batteryState.persistAcPowerKw(kw, { silent: true }).subscribe();
  }

  private reloadSuggestions(): void {
    this.suggestionsSub?.unsubscribe();
    this.suggestionsSub = this.homeData.getSuggestions().subscribe({
      next: (rows) => this.suggestionsSubject.next(rows),
      error: () => this.suggestionsSubject.next([]),
    });
  }

  private reloadPlanChart(): void {
    const day = todayIsoLocal();
    this.planSub?.unsubscribe();
    this.planSub = forkJoin({
      plan: this.api.getBatteryPlan(day),
      pv: this.api.getForecastHourly(day).pipe(catchError(() => of(null))),
    }).subscribe({
      next: ({ plan, pv }) => {
        this.planHours = plan.hours ?? [];
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
      },
    });
  }

  private scheduleRenderChart(attempt = 0): void {
    if (this.viewReady && this.canvasRef?.nativeElement && this.planHours.length) {
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
    const cheapMask = this.planHours.map((h) => (h.zone === 2 ? 100 : null));
    const zones = this.planHours.map((h) => h.zone);

    this.chart?.destroy();

    const cheapBands: Plugin = {
      id: 'cheapBandsHome',
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

  onSync() {
    this.homeData.triggerSync().subscribe();
  }

  formatKpiNumber(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return String(Math.round(value * 10) / 10);
  }

  socColor(soc: number | null | undefined, reserve: number = 20): string {
    if (soc === null || soc === undefined || Number.isNaN(soc)) return 'grid';
    if (soc >= 50) return 'moss';
    if (soc >= reserve) return 'warning';
    return 'cost';
  }

  socIcon(soc: number | null | undefined, reserve: number = 20): string {
    if (soc === null || soc === undefined || Number.isNaN(soc)) return 'battery-dead-outline';
    if (soc >= 70) return 'battery-full-outline';
    if (soc >= reserve) return 'battery-half-outline';
    return 'battery-dead-outline';
  }

  minutesAgo(date: Date | null): string {
    if (!date) return 'nigdy';
    const diffMs = Date.now() - date.getTime();
    const minutes = Math.max(0, Math.round(diffMs / 60000));
    if (minutes < 1) return 'przed chwilą';
    if (minutes === 1) return '1 minutę temu';
    return `${minutes} min temu`;
  }

  isNotToday(dayIso: string | null): boolean {
    if (!dayIso) return false;
    return dayIso !== todayIsoLocal();
  }

  formatDay(dayIso: string | null): string {
    if (!dayIso) return '';
    const [, month, day] = dayIso.split('-');
    return `${day}.${month}`;
  }
}
