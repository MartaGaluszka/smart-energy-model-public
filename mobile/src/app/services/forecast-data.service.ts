import { Injectable } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, Subject, concat, of, timer } from 'rxjs';
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
  loadKw: number;
}

export interface ApplianceThreshold {
  key: string;
  label: string;
  minKw: number;
}

export interface ForecastState {
  day: string;
  /** Wykres godzinowy — czeka na model. */
  loading: boolean;
  /** Sekcja „Prognoza vs rzeczywistość” — nie czeka na model. */
  compareLoading: boolean;
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
  /** Produkcja dnia z FoxESS — dotychczas gdy !isComplete, ostateczna suma po zamknięciu. */
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
/** Ponowne wejście na Prognozę w tym oknie nie gasi sekcji i nie liczy modelu od nowa. */
const FORECAST_FRESH_MS = 3 * 60 * 1000;

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
  private requested = todayIso();
  private readonly loads$ = new Subject<string>();
  private readonly fetchedAt = new Map<string, number>();
  private readonly memory = new Map<string, ForecastState>();
  /** Dzień, dla którego request już leci — drugie wejście na zakładkę go nie anuluje. */
  private inflight: string | null = null;

  private readonly state$ = new BehaviorSubject<ForecastState>({
    day: todayIso(),
    loading: true,
    compareLoading: true,
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
    // Nie pobieraj przy starcie aplikacji. Inaczej model rusza w tle i blokuje
    // tabele, zanim ktoś w ogóle wejdzie w Prognozę.
    this.loads$
      .pipe(switchMap((day) => this.fetchDay(day)))
      .subscribe((state) => {
        this.state$.next(state);
        if (!state.compareLoading) this.memory.set(state.day, state);
        if (!state.loading && this.inflight === state.day) this.inflight = null;
      });
  }

  getState(): Observable<ForecastState> {
    return this.state$.asObservable();
  }

  /** Ostatnio ZAŻĄDANY dzień (nie: ostatnio załadowany) — baza dla nawigacji ◀/▶. */
  get currentDay(): string {
    return this.requested;
  }

  shift(deltaDays: number): void {
    const target = shiftDay(this.currentDay, deltaDays);
    if (target < FIRST_DAY_WITH_DATA) return;
    if (target > maxFutureDayIso()) return;
    this.request(target);
  }

  goToday(): void {
    this.request(todayIso());
  }

  /** Dolna zakładka Prognoza — ten sam efekt co goToday (wywoływane z TabsPage). */
  focusPrognozaTab(): void {
    this.goToday();
  }

  loadDay(day: string): void {
    this.request(day);
  }

  /** Pociągnięcie w dół — świeże dane, ale bez gaszenia tabel, jeśli już są. */
  reload(): void {
    this.fetchedAt.delete(this.requested);
    this.inflight = null;
    this.request(this.requested, true);
  }

  private request(day: string, force = false): void {
    this.requested = day;
    if (!force && this.inflight === day) return;
    if (!force && this.hasFresh(day)) {
      const remembered = this.memory.get(day);
      if (remembered) {
        this.state$.next({
          ...remembered,
          canGoPrev: day > FIRST_DAY_WITH_DATA,
          canGoNext: day < maxFutureDayIso(),
        });
      }
      return;
    }
    this.inflight = day;
    this.publishPending(day);
    this.loads$.next(day);
  }

  private hasFresh(day: string): boolean {
    const at = this.fetchedAt.get(day) ?? 0;
    return this.memory.has(day) && at > 0 && Date.now() - at < FORECAST_FRESH_MS;
  }

  /** Znane tabele zostają na ekranie. Spinner sekcji tylko przy pierwszym dniu. */
  private publishPending(day: string): void {
    const flags = {
      canGoPrev: day > FIRST_DAY_WITH_DATA,
      canGoNext: day < maxFutureDayIso(),
    };
    const remembered = this.memory.get(day);
    if (remembered) {
      this.state$.next({
        ...remembered,
        ...flags,
        day,
        loading: true,
        compareLoading: false,
        error: null,
      });
      return;
    }
    this.state$.next({
      day,
      ...flags,
      loading: true,
      compareLoading: true,
      hours: [],
      totalKwh: null,
      daily: [],
      hourlyValidation: [],
      note: null,
      error: null,
      isComplete: true,
      actualSoFarKwh: null,
      applianceTips: [],
      applianceThresholds: [],
    });
  }

  /**
   * Najpierw walidacja (zapisane runy + jeden odczyt licznika). Sekcja porównania
   * pokazuje się, zanim model skończy wykres godzinowy.
   */
  private fetchDay(day: string): Observable<ForecastState> {
    const previous = this.state$.value;
    const sameDay = previous.day === day;
    const seed: ForecastState = {
      ...previous,
      day,
      loading: true,
      compareLoading: true,
      error: null,
      canGoPrev: day > FIRST_DAY_WITH_DATA,
      canGoNext: day < maxFutureDayIso(),
      ...(sameDay
        ? {}
        : {
            hours: [],
            totalKwh: null,
            daily: [],
            hourlyValidation: [],
            note: null,
            actualSoFarKwh: null,
            applianceTips: [],
            applianceThresholds: [],
          }),
    };

    return this.api.getForecastValidation(day).pipe(
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
      tap(() => this.fetchedAt.set(day, Date.now())),
      switchMap((validation) => {
        const compared: ForecastState = {
          ...seed,
          compareLoading: false,
          daily: validation.daily,
          hourlyValidation: validation.hourly,
          note: validation.note,
          isComplete: validation.is_complete,
          actualSoFarKwh:
            validation.actual_so_far_kwh
            ?? validation.daily.find((d) => d.actual_total_kwh !== null)?.actual_total_kwh
            ?? null,
        };
        const hourly$ = this.api.getForecastHourly(day).pipe(
          map((hourly) => ({
            ...compared,
            loading: false,
            hours: hourly.hours.map((h) => ({
              hour: h.hour,
              predictedKwh: h.predicted_kwh,
              actualKwh: h.actual_kwh,
              errorPct: h.error_pct,
            })),
            totalKwh: hourly.total_kwh,
            applianceTips: (hourly.appliance_tips ?? []).map((t) => ({
              hour: t.hour,
              predictedKwh: t.predicted_kwh,
              rank: t.rank,
              appliances: t.appliances,
              loadKw: t.load_kw ?? 0,
            })),
            applianceThresholds: (hourly.appliance_thresholds ?? []).map((t) => ({
              key: t.key,
              label: t.label,
              minKw: t.min_kw,
            })),
          })),
          catchError((err: HttpErrorResponse) =>
            of({
              ...compared,
              loading: false,
              hours: [],
              totalKwh: null,
              error: err?.error?.detail ?? 'Brak prognozy dla tego dnia (brak danych pogodowych).',
              applianceTips: [],
              applianceThresholds: [],
            }),
          ),
        );
        // Model wykresu startuje chwilę później. Szybka zmiana dnia nie kolejkuje
        // inferencji, która zasłaniałaby tabele.
        return concat(of(compared), timer(350).pipe(switchMap(() => hourly$)));
      }),
    );
  }
}
