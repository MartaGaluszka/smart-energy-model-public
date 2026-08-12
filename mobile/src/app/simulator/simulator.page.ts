import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { IonContent } from '@ionic/angular';
import { Chart, registerables } from 'chart.js';
import { Subscription } from 'rxjs';
import { TariffRates } from '../services/api.service';
import { SimulatorDataService, SimulatorState, TariffForm } from '../services/simulator-data.service';

/** `ion-datetime` (presentation="date") emituje ISO z komponentem czasu (np. "2026-06-01T00:00:00")
 *  — do reszty apki (API, porównania stringów dat) potrzebujemy tylko "YYYY-MM-DD". */
function toDateOnly(value: string | string[] | null | undefined): string {
  const v = Array.isArray(value) ? value[0] : value;
  return (v ?? '').slice(0, 10);
}

Chart.register(...registerables);

@Component({
  selector: 'app-simulator',
  templateUrl: './simulator.page.html',
  styleUrls: ['./simulator.page.scss'],
  standalone: false,
})
export class SimulatorPage implements AfterViewInit, OnDestroy {
  @ViewChild('billCanvas') private canvasRef?: ElementRef<HTMLCanvasElement>;
  @ViewChild('resultSection') private resultSectionRef?: ElementRef<HTMLElement>;
  @ViewChild(IonContent) private ionContent?: IonContent;

  state: SimulatorState | null = null;
  private chart?: Chart;
  private sub?: Subscription;
  private lastScrolledResult: unknown = null;

  constructor(private readonly simulator: SimulatorDataService) {}

  ngAfterViewInit(): void {
    this.sub = this.simulator.getState().subscribe((state) => {
      this.state = state;
      // setTimeout (a nie wywołanie synchroniczne) odkłada rysowanie na kolejny tick —
      // Angular musi najpierw zaktualizować DOM (odsłonić kartę z [hidden]="!s.result"),
      // inaczej Chart.js dostaje canvas o zerowych wymiarach / jeszcze niewidoczny.
      setTimeout(() => {
        this.renderChart(state);
        // Po każdej NOWEJ symulacji (nowy obiekt wyniku) przewiń do sekcji z wykresem —
        // "Policz rachunek" jest nad fold, więc bez tego użytkownik musi scrollować ręcznie.
        if (state.result && state.result !== this.lastScrolledResult) {
          this.lastScrolledResult = state.result;
          this.scrollToResult();
        }
      });
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.chart?.destroy();
  }

  onField(key: keyof TariffForm, value: string | number | null): void {
    const numericKeys: (keyof TariffForm)[] = [
      'price_zone1_day',
      'price_zone2_night',
      'distribution_zone1',
      'distribution_zone2',
      'subscription_fee_monthly',
      'power_fee_monthly',
      'oze_fee_kwh',
    ];
    if (numericKeys.includes(key)) {
      const n = value === '' || value === null || value === undefined ? null : Number(value);
      this.simulator.patchForm({ [key]: n } as Partial<TariffForm>);
      return;
    }
    this.simulator.patchForm({ [key]: value } as Partial<TariffForm>);
  }

  onPeriodStart(value: string): void {
    if (!this.state) return;
    this.simulator.setPeriod(toDateOnly(value), this.state.periodEnd);
  }

  onPeriodEnd(value: string): void {
    if (!this.state) return;
    this.simulator.setPeriod(this.state.periodStart, toDateOnly(value));
  }

  onValidFrom(value: string): void {
    this.onField('valid_from', toDateOnly(value));
  }

  saveRates(): void {
    this.simulator.saveRates();
  }

  startNewRate(): void {
    this.simulator.startNewRate();
  }

  editRate(rate: TariffRates): void {
    this.simulator.editRate(rate);
  }

  deleteRate(rate: TariffRates, ev: Event): void {
    ev.stopPropagation();
    this.simulator.deleteRate(rate.valid_from);
  }

  runSimulation(): void {
    this.simulator.runSimulation();
  }

  formatDate(iso: string): string {
    try {
      return new Date(`${iso}T00:00:00`).toLocaleDateString('pl-PL', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return iso;
    }
  }

  formatPln(v: number | null | undefined): string {
    if (v === null || v === undefined) return '—';
    return `${v.toFixed(2)} zł`;
  }

  formatKwh(v: number | null | undefined): string {
    if (v === null || v === undefined) return '—';
    return `${v.toFixed(1)} kWh`;
  }

  private async scrollToResult(): Promise<void> {
    const content = this.ionContent;
    const target = this.resultSectionRef?.nativeElement;
    if (!content || !target) return;

    const scrollEl = await content.getScrollElement();
    const y = target.getBoundingClientRect().top - scrollEl.getBoundingClientRect().top + scrollEl.scrollTop;
    content.scrollToPoint(0, Math.max(0, y - 12), 500);
  }

  private renderChart(state: SimulatorState): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas || !state.result) {
      this.chart?.destroy();
      this.chart = undefined;
      return;
    }

    // Wykres pokazuje kwoty BRUTTO (z VAT) — to ostateczna kwota "do zapłaty"; netto widać
    // obok w KPI, tuż pod przyciskiem "Policz rachunek" (T2.7).
    const { cost_no_pv_gross_pln, cost_with_pv_gross_pln, savings_gross_pln } = state.result;
    const data = [cost_no_pv_gross_pln, cost_with_pv_gross_pln, Math.max(0, savings_gross_pln)];
    const colors = ['#3D4450', '#E6A012', '#4F6F52']; // grid / solar / moss

    this.chart?.destroy();
    this.chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: ['Bez paneli', 'Z PV', 'Oszczędność'],
        datasets: [
          {
            label: 'PLN',
            data,
            backgroundColor: colors,
            borderRadius: 6,
            maxBarThickness: 56,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: 'Koszt rachunku w okresie',
            color: '#2B2E33',
            font: { size: 13, weight: 'bold' },
          },
          legend: { display: false },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#5C636A', font: { size: 11 } },
          },
          y: {
            beginAtZero: true,
            grid: { color: '#E3DFD6' },
            ticks: {
              color: '#5C636A',
              font: { size: 10 },
              callback: (v) => `${v} zł`,
            },
            title: { display: true, text: 'Koszt (zł)', color: '#5C636A', font: { size: 11 } },
          },
        },
      },
    });
  }
}
