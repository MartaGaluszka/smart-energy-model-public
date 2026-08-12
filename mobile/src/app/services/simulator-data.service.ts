import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { catchError, finalize, tap } from 'rxjs/operators';
import {
  ApiService,
  SimulateBillResponse,
  TariffRates,
  TariffRatesCreate,
} from './api.service';
import { todayIsoLocal, shiftIsoDate } from '../utils/date-utils';

export interface TariffForm {
  valid_from: string;
  tariff_name: string;
  price_zone1_day: number | null;
  price_zone2_night: number | null;
  distribution_zone1: number | null;
  distribution_zone2: number | null;
  subscription_fee_monthly: number | null;
  power_fee_monthly: number | null;
  oze_fee_kwh: number | null;
  vat_mode: string;
  notes: string | null;
}

export interface SimulatorState {
  loadingRates: boolean;
  savingRates: boolean;
  simulating: boolean;
  form: TariffForm;
  ratesSource: string | null;
  /** Wszystkie zapisane stawki użytkownika (może zmieniać taryfę kilka razy w roku) — najnowsza pierwsza. */
  history: TariffRates[];
  loadingHistory: boolean;
  deletingValidFrom: string | null;
  periodStart: string;
  periodEnd: string;
  result: SimulateBillResponse | null;
  error: string | null;
  saveMessage: string | null;
}

function emptyForm(): TariffForm {
  return {
    valid_from: todayIsoLocal(),
    tariff_name: 'G12w',
    price_zone1_day: null,
    price_zone2_night: null,
    distribution_zone1: null,
    distribution_zone2: null,
    subscription_fee_monthly: null,
    power_fee_monthly: null,
    oze_fee_kwh: null,
    vat_mode: 'net',
    notes: null,
  };
}

function ratesToForm(r: TariffRates): TariffForm {
  return {
    valid_from: r.valid_from || todayIsoLocal(),
    tariff_name: r.tariff_name || 'G12w',
    price_zone1_day: r.price_zone1_day,
    price_zone2_night: r.price_zone2_night,
    distribution_zone1: r.distribution_zone1,
    distribution_zone2: r.distribution_zone2,
    subscription_fee_monthly: r.subscription_fee_monthly,
    power_fee_monthly: r.power_fee_monthly,
    oze_fee_kwh: r.oze_fee_kwh,
    vat_mode: r.vat_mode || 'net',
    notes: r.notes,
  };
}

function toNullableNumber(v: number | null | undefined | string): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function formToCreate(f: TariffForm): TariffRatesCreate {
  return {
    valid_from: f.valid_from,
    tariff_name: f.tariff_name || 'G12w',
    price_zone1_day: Number(f.price_zone1_day),
    price_zone2_night: Number(f.price_zone2_night),
    distribution_zone1: toNullableNumber(f.distribution_zone1 as number | null),
    distribution_zone2: toNullableNumber(f.distribution_zone2 as number | null),
    subscription_fee_monthly: toNullableNumber(f.subscription_fee_monthly as number | null),
    power_fee_monthly: toNullableNumber(f.power_fee_monthly as number | null),
    oze_fee_kwh: toNullableNumber(f.oze_fee_kwh as number | null),
    vat_mode: f.vat_mode || 'net',
    notes: f.notes,
  };
}

/**
 * Stan ekranu Symulator (T2.4–T2.5): historia stawek z /tariff/rates(/history) + wynik /simulate/bill.
 *
 * Taryfa zmienia się w ciągu roku (nowa umowa, podwyżka) — dlatego formularz to "dodaj/edytuj
 * JEDNĄ stawkę z konkretną datą Ważne od", a nie jedyny stan. Można zapisać kilka stawek
 * z różnymi datami; `POST /tariff/rates` sam dopasowuje właściwą stawkę do każdego pod-okresu
 * przy liczeniu rachunku (zob. `api/services/bill_simulator.py::_resolve_segments`).
 */
@Injectable({ providedIn: 'root' })
export class SimulatorDataService {
  // Serwis jest singletonem (providedIn: 'root') — stan (w tym `saveMessage`) przeżywa
  // nawigację między tabami. Bez auto-czyszczenia komunikat "Stawka zapisana." zostawałby
  // widoczny w nieskończoność przy KAŻDYM powrocie na ekran, nie tylko zaraz po zapisie.
  private saveMessageTimer?: ReturnType<typeof setTimeout>;

  private readonly state$ = new BehaviorSubject<SimulatorState>({
    loadingRates: false,
    savingRates: false,
    simulating: false,
    form: emptyForm(),
    ratesSource: null,
    history: [],
    loadingHistory: false,
    deletingValidFrom: null,
    periodStart: shiftIsoDate(todayIsoLocal(), -30),
    periodEnd: todayIsoLocal(),
    result: null,
    error: null,
    saveMessage: null,
  });

  constructor(private readonly api: ApiService) {
    this.loadRates();
    this.loadHistory();
  }

  getState(): Observable<SimulatorState> {
    return this.state$.asObservable();
  }

  get snapshot(): SimulatorState {
    return this.state$.value;
  }

  /** Pokazuje komunikat na chwilę i sam go czyści — patrz komentarz przy `saveMessageTimer`. */
  private flashSaveMessage(msg: string): void {
    clearTimeout(this.saveMessageTimer);
    this.state$.next({ ...this.state$.value, saveMessage: msg });
    this.saveMessageTimer = setTimeout(() => {
      if (this.state$.value.saveMessage === msg) {
        this.state$.next({ ...this.state$.value, saveMessage: null });
      }
    }, 3500);
  }

  patchForm(partial: Partial<TariffForm>): void {
    clearTimeout(this.saveMessageTimer);
    this.state$.next({
      ...this.state$.value,
      form: { ...this.state$.value.form, ...partial },
      saveMessage: null,
    });
  }

  setPeriod(start: string, end: string): void {
    this.state$.next({ ...this.state$.value, periodStart: start, periodEnd: end, error: null });
  }

  /** Wypełnia formularz jedną z historycznych stawek — do edycji/poprawki. */
  editRate(rate: TariffRates): void {
    clearTimeout(this.saveMessageTimer);
    this.state$.next({ ...this.state$.value, form: ratesToForm(rate), saveMessage: null, error: null });
  }

  /** Czyści formularz, żeby dodać NOWĄ stawkę (inna data "Ważne od") bez ryzyka nadpisania obecnej. */
  startNewRate(): void {
    clearTimeout(this.saveMessageTimer);
    this.state$.next({ ...this.state$.value, form: emptyForm(), saveMessage: null, error: null });
  }

  loadRates(): void {
    this.state$.next({ ...this.state$.value, loadingRates: true, error: null });
    this.api
      .getTariffRates()
      .pipe(
        tap((rates) => {
          this.state$.next({
            ...this.state$.value,
            loadingRates: false,
            form: ratesToForm(rates),
            ratesSource: rates.source,
          });
        }),
        catchError((err) => {
          this.state$.next({
            ...this.state$.value,
            loadingRates: false,
            error: err?.error?.detail ?? 'Nie udało się pobrać stawek.',
          });
          return of(null);
        }),
      )
      .subscribe();
  }

  loadHistory(): void {
    this.state$.next({ ...this.state$.value, loadingHistory: true });
    this.api
      .getTariffRatesHistory()
      .pipe(
        tap((history) => {
          this.state$.next({ ...this.state$.value, loadingHistory: false, history });
        }),
        catchError(() => {
          this.state$.next({ ...this.state$.value, loadingHistory: false });
          return of(null);
        }),
      )
      .subscribe();
  }

  saveRates(): void {
    const body = formToCreate(this.state$.value.form);
    if (!Number.isFinite(body.price_zone1_day) || !Number.isFinite(body.price_zone2_night)) {
      this.state$.next({ ...this.state$.value, error: 'Podaj ceny energii strefa 1 i 2.' });
      return;
    }
    this.state$.next({ ...this.state$.value, savingRates: true, error: null, saveMessage: null });
    this.api
      .saveTariffRates(body)
      .pipe(
        tap((rates) => {
          this.state$.next({
            ...this.state$.value,
            savingRates: false,
            form: ratesToForm(rates),
            ratesSource: rates.source,
          });
          this.flashSaveMessage('Stawka zapisana.');
          this.loadHistory();
        }),
        catchError((err) => {
          this.state$.next({
            ...this.state$.value,
            savingRates: false,
            error: err?.error?.detail ?? 'Zapis stawek nie powiódł się.',
          });
          return of(null);
        }),
        finalize(() => {
          if (this.state$.value.savingRates) {
            this.state$.next({ ...this.state$.value, savingRates: false });
          }
        }),
      )
      .subscribe();
  }

  deleteRate(validFrom: string): void {
    this.state$.next({ ...this.state$.value, deletingValidFrom: validFrom, error: null });
    this.api
      .deleteTariffRates(validFrom)
      .pipe(
        tap(() => {
          this.state$.next({ ...this.state$.value, deletingValidFrom: null });
          this.flashSaveMessage('Stawka usunięta.');
          this.loadHistory();
        }),
        catchError((err) => {
          this.state$.next({
            ...this.state$.value,
            deletingValidFrom: null,
            error: err?.error?.detail ?? 'Nie udało się usunąć stawki.',
          });
          return of(null);
        }),
      )
      .subscribe();
  }

  /**
   * Zawsze liczy rachunek na podstawie zapisanej HISTORII stawek (bez `rates_override`) —
   * backend sam dobiera właściwą stawkę do każdego pod-okresu (`_resolve_segments`), więc
   * zmiana taryfy w połowie okresu jest uwzględniona automatycznie. Niezapisane zmiany w
   * formularzu NIE wpływają na wynik, dopóki nie klikniesz "Zapisz stawki".
   */
  runSimulation(): void {
    const s = this.state$.value;
    if (s.periodStart > s.periodEnd) {
      this.state$.next({ ...this.state$.value, error: 'Okres: data początku nie może być po dacie końca.' });
      return;
    }

    this.state$.next({ ...this.state$.value, simulating: true, error: null, result: null });
    this.api
      .simulateBill({
        period_start: s.periodStart,
        period_end: s.periodEnd,
        rates_override: null,
      })
      .pipe(
        tap((result) => {
          this.state$.next({ ...this.state$.value, simulating: false, result });
        }),
        catchError((err) => {
          const detail = err?.error?.detail;
          const msg =
            typeof detail === 'string'
              ? detail
              : detail?.message ?? 'Symulacja nie powiodła się (brak danych FoxESS w okresie?).';
          this.state$.next({ ...this.state$.value, simulating: false, error: msg });
          return of(null);
        }),
      )
      .subscribe();
  }
}
