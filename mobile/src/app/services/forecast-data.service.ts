import { Injectable } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, forkJoin, of } from 'rxjs';
import { catchError, map, switchMap, tap } from 'rxjs/operators';
import {
  ApiService,
  ForecastValidationDailyRow,
  ForecastValidationHourlyRow,
} from './api.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';

export interface ForecastHourPoint {
  hour: number;
  predictedKwh: number;
  actualKwh: number | null;
  errorPct: number | null;
}

export interface ApplianceTip {
  hour: number;
  predictedKwh: number;
  rank: number;
  appliances: string[];
}

export interface ApplianceThreshold {
  key: string;
  label: string;
  minKw: number;
}

export interface ForecastState {
  day: string;
  loading: boolean;
  hours: ForecastHourPoint[];
  totalKwh: number | null;
  daily: ForecastValidationDailyRow[];
  hourlyValidation: ForecastValidationHourlyRow[];
  note: string | null;
  /** Komunikat błędu (np. brak danych pogodowych) — null gdy wszystko OK. */
  error: string | null;
  /** false gdy dalsze cofanie nie ma sensu (osiągnięto pierwszy dzień z danymi). */
  canGoPrev: boolean;
  /** false gdy dalsze przewijanie w przód nie ma sensu (osiągnięto max outlook). */
  canGoNext: boolean;
  /** false = dzień jeszcze trwa — patrz `actualSoFarKwh`; `daily[].actual_total_kwh`/error_*
   *  są wtedy null (pojawią się dopiero po wieczornej synchronizacji, T1.17/T1.18). */
  isComplete: boolean;
  /** Produkcja dotychczasowa (jak "Dzienna produkcja" w apce FoxESS) — tylko gdy !isComplete. */
  actualSoFarKwh: number | null;
  /** T1.20 — kiedy włączyć AGD. */
  applianceTips: ApplianceTip[];
  applianceThresholds: ApplianceThreshold[];
}

/** Pierwszy dzień, dla którego istnieje zarchiwizowana prognoza (forecast_history.csv). */
export const FIRST_DAY_WITH_DATA = '2026-07-14';

/** Ile dni do przodu względem dziś pokazujemy outlook (jutro + pojutrze = 2). */
export const MAX_FUTURE_DAYS = 2;

const todayIso = todayIsoLocal;
const shiftDay = shiftIsoDate;

function maxFutureDayIso(): string {
  return shiftDay(todayIso(), MAX_FUTURE_DAYS);
}

/**
 * Most między ekranem Prognoza (tab3, T1.12–T1.14) a `/forecast/hourly` + `/forecast/validation`.
 * Łączy oba wywołania w jeden stan UI; błąd jednego z nich (np. brak archiwum prognozy dla
 * bardzo starego dnia) nie blokuje drugiego — degradujemy częściowo, nie do zera.
 *
 * `requestedDay$` (intencja, aktualizowana SYNCHRONICZNIE po każdym kliknięciu ◀/▶) jest
 * rozdzielone od `state$` (wynik, aktualizowany dopiero po odpowiedzi API) i połączone przez
 * `switchMap` — dzięki temu szybkie klikanie nie gubi pozycji: nawigacja zawsze liczy się
 * względem ostatnio KLIKNIĘTEGO dnia, a nie ostatnio ZAŁADOWANEGO (odpowiedzi mogą wracać
 * w innej kolejności niż kliknięcia, bo dni bez danych zwracają błąd szybciej niż te z modelem).
 */
@Injectable({ providedIn: 'root' })
export class ForecastDataService {
  private readonly requestedDay$ = new BehaviorSubject<string>(todayIso());
  private readonly state$ = new BehaviorSubject<ForecastState>({
    day: todayIso(),
    loading: true,
    hours: [],
    totalKwh: null,
    daily: [],
    hourlyValidation: [],
    note: null,
    error: null,
    canGoPrev: todayIso() > FIRST_DAY_WITH_DATA,
    canGoNext: todayIso() < maxFutureDayIso(),
    isComplete: true,
    actualSoFarKwh: null,
    applianceTips: [],
    applianceThresholds: [],
  });

  constructor(private readonly api: ApiService) {
    this.requestedDay$
      .pipe(
        tap((day) =>
          this.state$.next({
            ...this.state$.value,
            day,
            loading: true,
            error: null,
            canGoPrev: day > FIRST_DAY_WITH_DATA,
            canGoNext: day < maxFutureDayIso(),
          }),
        ),
        switchMap((day) => this.fetchDay(day)),
      )
      .subscribe((state) => this.state$.next(state));
  }

  getState(): Observable<ForecastState> {
    return this.state$.asObservable();
  }

  /** Ostatnio ZAŻĄDANY dzień (nie: ostatnio załadowany) — baza dla nawigacji ◀/▶. */
  get currentDay(): string {
    return this.requestedDay$.value;
  }

  shift(deltaDays: number): void {
    const target = shiftDay(this.currentDay, deltaDays);
    if (target < FIRST_DAY_WITH_DATA) return;
    if (target > maxFutureDayIso()) return;
    this.requestedDay$.next(target);
  }

  goToday(): void {
    this.requestedDay$.next(todayIso());
  }

  loadDay(day: string): void {
    this.requestedDay$.next(day);
  }

  /**
   * Wymusza ponowne pobranie danych dla aktualnie wyświetlanego dnia, bez zmiany dnia.
   * `BehaviorSubject.next()` emituje zawsze (bez `distinctUntilChanged`), więc wywołanie
   * z tą samą wartością i tak przechodzi przez `switchMap` i odpytuje API na nowo —
   * potrzebne np. przy powrocie na zakładkę Prognoza (dane z rana/południa/popołudnia
   * uzupełniają się w ciągu dnia po kolejnych synchronizacjach) albo przy pull-to-refresh.
   */
  reload(): void {
    this.requestedDay$.next(this.requestedDay$.value);
  }

  private fetchDay(day: string): Observable<ForecastState> {
    return forkJoin({
      hourly: this.api.getForecastHourly(day).pipe(
        catchError((err: HttpErrorResponse) =>
          of({
            day,
            hours: [] as {
              hour: number;
              predicted_kwh: number;
              prediction_source: string;
              actual_kwh: number | null;
              error_pct: number | null;
            }[],
            total_kwh: null as unknown as number,
            model_path: '',
            appliance_tips: [],
            appliance_thresholds: [],
            __error: err?.error?.detail ?? 'Brak prognozy dla tego dnia (brak danych pogodowych).',
          }),
        ),
      ),
      validation: this.api.getForecastValidation(day).pipe(
        catchError(() =>
          of({
            day,
            daily: [],
            hourly: [],
            peaks: [],
            note: 'Walidacja niedostępna dla tego dnia.',
            is_complete: true,
            actual_so_far_kwh: null,
          }),
        ),
      ),
    }).pipe(
      map(({ hourly, validation }) => {
        const hourlyError = (hourly as { __error?: string }).__error ?? null;
        return {
          day,
          loading: false,
          hours: hourly.hours.map((h) => ({
            hour: h.hour,
            predictedKwh: h.predicted_kwh,
            actualKwh: h.actual_kwh,
            errorPct: h.error_pct,
          })),
          totalKwh: hourlyError ? null : hourly.total_kwh,
          daily: validation.daily,
          hourlyValidation: validation.hourly,
          note: validation.note,
          error: hourlyError,
          canGoPrev: day > FIRST_DAY_WITH_DATA,
          canGoNext: day < maxFutureDayIso(),
          isComplete: validation.is_complete,
          actualSoFarKwh: validation.actual_so_far_kwh,
          applianceTips: (hourly.appliance_tips ?? []).map((t) => ({
            hour: t.hour,
            predictedKwh: t.predicted_kwh,
            rank: t.rank,
            appliances: t.appliances,
          })),
          applianceThresholds: (hourly.appliance_thresholds ?? []).map((t) => ({
            key: t.key,
            label: t.label,
            minKw: t.min_kw,
          })),
        };
      }),
    );
  }
}
