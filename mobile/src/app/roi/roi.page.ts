import { Component, OnInit } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { switchMap } from 'rxjs';
import { addIcons } from 'ionicons';
import {
  analyticsOutline,
  cashOutline,
  constructOutline,
  giftOutline,
  informationCircleOutline,
} from 'ionicons/icons';
import { ApiService, RoiAssumptions, RoiCalculateResponse } from '../services/api.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';

function toDateOnly(value: string | string[] | null | undefined): string {
  const v = Array.isArray(value) ? value[0] : value;
  return (v ?? '').slice(0, 10);
}

function num(value: string | number | null | undefined): number {
  if (value === '' || value === null || value === undefined) return 0;
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, n) : 0;
}

@Component({
  selector: 'app-roi',
  templateUrl: './roi.page.html',
  styleUrls: ['./roi.page.scss'],
  standalone: false,
})
export class RoiPage implements OnInit {
  /**
   * Panele 8 800 zł brutto (mimo ceny domu — weszły w Mój Prąd i ulgę).
   * Zestaw H3 + EP11 + AZR + DTSU: 32 820 zł.
   * Mój Prąd i ulga 32% liczone z sumy tych dwóch kwot.
   * OPEX to przegląd raz na 5 lat, nie rachunek za prąd (600 zł / 5 = 120 zł/rok).
   */
  panels = 8800;
  inverterBattery = 32820;
  opex = 120;
  /** Edytowalne; startowo: 50% kosztów z limitem PV/magazyn + 32% ulgi. */
  mojPrad = 0;
  taxRelief = 0;
  /**
   * Mój Prąd 6 (jak w ofercie instalatora + reguły NFOŚiGW):
   * do 50% kosztów kwalifikowanych, nie więcej niż 7 000 zł (PV) i 16 000 zł (magazyn).
   * Ulga termo: 32% od sumy po dotacji.
   */
  readonly mojPradRate = 0.5;
  readonly mojPradPvCap = 7000;
  readonly mojPradStorageCap = 16000;
  readonly taxReliefRate = 0.32;
  horizon = 15;
  periodStart = shiftIsoDate(todayIsoLocal(), -364);
  periodEnd = todayIsoLocal();

  loading = true;
  calculating = false;
  error: string | null = null;
  result: RoiCalculateResponse | null = null;

  private inflationPct = 0;
  private sellerBaseline: number | null = null;

  constructor(private readonly api: ApiService) {
    addIcons({
      cashOutline,
      giftOutline,
      constructOutline,
      analyticsOutline,
      informationCircleOutline,
    });
    this.syncSubsidiesFromCapex();
  }

  ngOnInit(): void {
    this.api.getRoiAssumptions().subscribe({
      next: (row) => {
        this.applyAssumptions(row);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  get grossCapex(): number {
    return this.roundPln(this.panels + this.inverterBattery);
  }

  /** Dotacja: 50% kosztów PV i magazynu, każdy z własnym limitem (7k / 16k). */
  get suggestedMojPradPv(): number {
    return this.roundPln(Math.min(this.panels * this.mojPradRate, this.mojPradPvCap));
  }

  get suggestedMojPradStorage(): number {
    return this.roundPln(
      Math.min(this.inverterBattery * this.mojPradRate, this.mojPradStorageCap),
    );
  }

  get suggestedMojPrad(): number {
    return this.roundPln(this.suggestedMojPradPv + this.suggestedMojPradStorage);
  }

  /** 32% od sumy pomniejszonej o Mój Prąd z limitu (sugerowany). */
  get suggestedTaxRelief(): number {
    return this.roundPln((this.grossCapex - this.suggestedMojPrad) * this.taxReliefRate);
  }

  get netCapex(): number {
    return this.roundPln(Math.max(0, this.grossCapex - this.mojPrad - this.taxRelief));
  }

  get withinHorizon(): boolean {
    const years = this.result?.remaining_years;
    return years != null && years <= this.horizon;
  }

  /** Procent kosztów początkowych już spłacony w wybranym okresie (0–100). */
  get recoveryPct(): number {
    const r = this.result;
    if (!r) return 0;
    const total = (r.recovered_pln ?? 0) + (r.remaining_pln ?? 0);
    if (total <= 0) return 0;
    return Math.min(100, Math.max(0, (r.recovered_pln / total) * 100));
  }

  onNumber(
    field: 'panels' | 'inverterBattery' | 'opex' | 'mojPrad' | 'taxRelief',
    value: string | number | null,
  ): void {
    this[field] = num(value);
    if (field === 'panels' || field === 'inverterBattery') {
      this.syncSubsidiesFromCapex();
    } else if (field === 'mojPrad') {
      // Po zmianie Mój Prąd — przelicz ulgę 32% od reszty.
      this.taxRelief = this.roundPln((this.grossCapex - this.mojPrad) * this.taxReliefRate);
    }
    this.result = null;
  }

  /** Przywróć Mój Prąd i ulgę z aktualnych kosztów początkowych. */
  resetSubsidiesFromCapex(): void {
    this.syncSubsidiesFromCapex();
    this.result = null;
  }

  onHorizon(value: number): void {
    this.horizon = Math.min(25, Math.max(5, Math.round(value)));
  }

  onPeriodStart(value: string | string[] | null): void {
    this.periodStart = toDateOnly(value);
    this.result = null;
  }

  onPeriodEnd(value: string | string[] | null): void {
    this.periodEnd = toDateOnly(value);
    this.result = null;
  }

  formatPln(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(value)) return '—';
    return value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  calculate(): void {
    this.calculating = true;
    this.error = null;
    const body: RoiAssumptions = {
      capex_pln: this.netCapex,
      battery_capex_pln: null,
      opex_pln_year: this.opex,
      inflation_pct: this.inflationPct,
      seller_baseline_pln_year: this.sellerBaseline,
    };
    this.api.putRoiAssumptions(body).pipe(
      switchMap(() => this.api.calculateRoi(this.periodStart, this.periodEnd)),
    ).subscribe({
      next: (data) => {
        this.result = data;
        this.calculating = false;
      },
      error: (err: HttpErrorResponse) => {
        this.calculating = false;
        const detail = err.error?.detail;
        this.error = typeof detail === 'string'
          ? detail
          : 'Nie udało się policzyć zwrotu. Sprawdź, czy API działa i czy w wybranym okresie są dane.';
      },
    });
  }

  private applyAssumptions(row: RoiAssumptions): void {
    this.inflationPct = row.inflation_pct ?? 0;
    this.sellerBaseline = row.seller_baseline_pln_year;
    const battery = row.battery_capex_pln ?? 0;
    const capex = row.capex_pln ?? 0;
    const known = (capex === 0 && battery === 0)
      || (capex === 8800 && battery === 32000)
      || (capex === 40800 && battery === 0)
      || (capex === 11158 && battery === 0)
      || (capex === 12382 && battery === 0)
      || (capex === 12661.6 && battery === 0);
    if (!known) {
      // API trzyma już net CAPEX — nie rozbijamy wstecz; zostaw defaults + sync ulg.
      this.opex = row.opex_pln_year ?? 0;
    }
    this.syncSubsidiesFromCapex();
  }

  private syncSubsidiesFromCapex(): void {
    this.mojPrad = this.suggestedMojPrad;
    this.taxRelief = this.roundPln((this.grossCapex - this.mojPrad) * this.taxReliefRate);
  }

  private roundPln(value: number): number {
    return Math.round(value * 100) / 100;
  }
}
