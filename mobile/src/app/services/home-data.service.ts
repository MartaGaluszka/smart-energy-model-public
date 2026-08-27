import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, catchError, map, of, switchMap, tap, timeout } from 'rxjs';
import { ApiService, BatterySuggestionResponse, FoxOverviewResponse, NotificationDto } from './api.service';
import { toLocalIsoDate } from '../utils/date-utils';

export interface HomeKpi {
  productionKwh: number;
  socPercent: number;
  gridImportKwh: number;
  gridExportKwh: number;
}

export interface Suggestion {
  id: string;
  kind: string;
  title: string;
  body: string;
}

export interface SyncStatus {
  lastSyncedAt: Date | null;
  syncing: boolean;
  offline: boolean;
  /** ISO data dnia, z którego faktycznie pochodzi KPI (może być wcześniejszy niż "dziś"). */
  dataDay: string | null;
  /** Komunikat do pokazania użytkownikowi po nieudanej/zbyt długiej/pominiętej synchronizacji. */
  message: string | null;
  /** 'error' — czerwony komunikat (timeout/fail); 'info' — neutralny (np. "dane aktualne"). */
  messageKind: 'error' | 'info' | null;
}

const FALLBACK_KPI: HomeKpi = {
  productionKwh: 34.4,
  socPercent: 62,
  gridImportKwh: 1.2,
  gridExportKwh: 18.5,
};

/** Zawsze pokaż kartę — *ngIf ukrywa ją przy null (timeout Fox / 500). */
const FALLBACK_BATTERY: BatterySuggestionResponse = {
  as_of: new Date().toISOString(),
  season: 'summer',
  season_mode: 'auto',
  soc_now_percent: null,
  soc_min_percent: 20,
  soc_reserve_percent: 20,
  soc_target_percent: 80,
  soc_min_evening_percent: 50,
  force_charge_night_recommended: false,
  force_charge_night_label: 'pomiń — wystarczy PV',
  force_charge_afternoon_recommended: false,
  force_charge_afternoon_label: 'rzadko potrzebne',
  force_charge_night_start: null,
  force_charge_night_end: null,
  force_charge_night_minutes: null,
  force_charge_afternoon_window: null,
  charge_when_summary: 'Dziś bez doładowania z sieci — wystarczy PV / rezerwa SE',
  fc_max_minutes: 15,
  fc_night_start_hour: 22,
  soc16_alert: false,
  soc16_hour_passed: false,
  soc16_percent: null,
  soc16_title: null,
  soc16_body: null,
  wait_for_cheap: false,
  next_cheap_window: null,
  recommendation: 'REŻIM LATO',
  action:
    'Trzymaj min 20% na noc (rezerwa). Ładowanie z sieci tylko gdy bateria spada poniżej 20% i jutro słabe PV. System tylko doradza — decyzja należy do Ciebie.',
  automation_enabled: false,
  note: 'Sugestia — nie wykonano automatycznie (advise-only).',
};

// FoxESS Cloud bywa limitowane (40402) — istniejąca logika sync w src/data/foxess_fetch_all.py
// wtedy retry'uje z narastającym backoffem, co może zająć naprawdę długo (nawet >10 min).
// Klient nie może na to czekać w nieskończoność — po timeoucie pokazujemy komunikat
// i cofamy spinner, ale sync może się jeszcze dokończyć w tle po stronie API.
const SYNC_TIMEOUT_MS = 15_000;
const OVERVIEW_TIMEOUT_MS = 10_000;
const LOOKBACK_DAYS = 5;

/**
 * Most między UI (Home / tab1) i `api/` (FastAPI, Faza 0 — patrz §12 dok. projektowego).
 * Jeśli backend jest nieosiągalny, serwis cofa się do danych demonstracyjnych — flaga
 * `offline` w SyncStatus sygnalizuje to w widoku. Jeśli backend działa, ale dla "dziś"
 * nie ma jeszcze zapisanych danych (sync jeszcze się nie wykonał), automatycznie
 * pokazujemy najnowszy dzień z realnymi danymi (`dataDay`) — nigdy fałszywych liczb
 * pod etykietą "dziś".
 */
@Injectable({ providedIn: 'root' })
export class HomeDataService {
  private readonly kpi$ = new BehaviorSubject<HomeKpi>(FALLBACK_KPI);
  private readonly battery$ = new BehaviorSubject<BatterySuggestionResponse | null>(FALLBACK_BATTERY);
  private readonly sync$ = new BehaviorSubject<SyncStatus>({
    lastSyncedAt: null,
    syncing: false,
    offline: false,
    dataDay: null,
    message: null,
    messageKind: null,
  });

  constructor(private readonly api: ApiService) {
    this.refreshOverview();
    this.refreshBatterySuggestion();
  }

  getKpi(): Observable<HomeKpi> {
    return this.kpi$.asObservable();
  }

  getSyncStatus(): Observable<SyncStatus> {
    return this.sync$.asObservable();
  }

  getSuggestions(): Observable<Suggestion[]> {
    return this.api.getNotifications().pipe(
      map((rows) => rows.filter((r) => r.read_at === null).map(this.toSuggestion)),
      catchError(() => of([] as Suggestion[])),
    );
  }

  getBatterySuggestion(): Observable<BatterySuggestionResponse | null> {
    return this.battery$.asObservable();
  }

  refreshBatterySuggestion(): void {
    this.api.getBatterySuggestion().pipe(timeout(OVERVIEW_TIMEOUT_MS)).subscribe({
      next: (row) => this.battery$.next(row),
      error: () => {
        if (this.battery$.value === null) {
          this.battery$.next(FALLBACK_BATTERY);
        }
      },
    });
  }

  /**
   * Odpowiada `POST /api/v1/foxess/sync` (TA.3) — bez zakresu dat: backend sam dobiera
   * brakujący odcinek (od ostatniego zapisanego dnia do dziś) i pomija wywołanie FoxESS,
   * jeśli dane są już aktualne (cooldown po stronie API) — patrz `foxess_sync.sync_incremental`.
   */
  triggerSync(): Observable<SyncStatus> {
    this.sync$.next({ ...this.sync$.value, syncing: true, message: null, messageKind: null });
    return this.api.syncFox().pipe(
      timeout(SYNC_TIMEOUT_MS),
      tap((res) => this.refreshOverview(res.status === 'skipped' ? res.message : null, 'info')),
      catchError((err) => {
        const timedOut = err?.name === 'TimeoutError';
        this.sync$.next({
          ...this.sync$.value,
          syncing: false,
          message: timedOut
            ? 'Synchronizacja z FoxESS trwa długo (limit API Fox) — spróbuj ponownie za kilka minut.'
            : 'Synchronizacja nie powiodła się. Sprawdź połączenie z API.',
          messageKind: 'error',
        });
        return of(null);
      }),
      map(() => this.sync$.value),
    );
  }

  private refreshOverview(
    message: string | null = null,
    messageKind: 'error' | 'info' | null = null,
  ): void {
    this.sync$.next({ ...this.sync$.value, syncing: true });
    this.fetchLatestAvailableOverview(0).subscribe({
      next: (overview) => {
        if (!overview) {
          this.sync$.next({ ...this.sync$.value, syncing: false, offline: true });
          return;
        }
        this.kpi$.next({
          productionKwh: overview.pv_kwh ?? FALLBACK_KPI.productionKwh,
          socPercent: overview.soc_percent ?? FALLBACK_KPI.socPercent,
          gridImportKwh: overview.grid_import_kwh ?? FALLBACK_KPI.gridImportKwh,
          gridExportKwh: overview.grid_export_kwh ?? FALLBACK_KPI.gridExportKwh,
        });
        this.sync$.next({
          lastSyncedAt: overview.last_synced_at ? new Date(overview.last_synced_at) : null,
          syncing: false,
          offline: false,
          dataDay: overview.day,
          message,
          messageKind,
        });
        this.refreshBatterySuggestion();
      },
      error: (err) => {
        console.warn('[HomeDataService] api/foxess/overview niedostępne — dane demo.', err);
        this.sync$.next({ ...this.sync$.value, syncing: false, offline: true });
      },
    });
  }

  /** Szuka od "dziś" wstecz (max LOOKBACK_DAYS) pierwszego dnia z realnymi danymi. */
  private fetchLatestAvailableOverview(daysBack: number): Observable<FoxOverviewResponse | null> {
    const day = new Date();
    day.setDate(day.getDate() - daysBack);
    const dayIso = toLocalIsoDate(day);

    return this.api.getFoxOverview(dayIso).pipe(
      timeout(OVERVIEW_TIMEOUT_MS),
      switchMap((overview) => {
        if (overview.has_data || daysBack >= LOOKBACK_DAYS) {
          return of(overview);
        }
        return this.fetchLatestAvailableOverview(daysBack + 1);
      }),
    );
  }

  private toSuggestion(row: NotificationDto): Suggestion {
    return { id: String(row.id), kind: row.notif_type, title: row.title, body: row.body };
  }
}
