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
  private readonly battery$ = new BehaviorSubject<BatterySuggestionResponse | null>(null);
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
      map((rows) => rows.map(this.toSuggestion)),
      catchError(() => of([] as Suggestion[])),
    );
  }

  getBatterySuggestion(): Observable<BatterySuggestionResponse | null> {
    return this.battery$.asObservable();
  }

  refreshBatterySuggestion(): void {
    this.api.getBatterySuggestion().pipe(timeout(OVERVIEW_TIMEOUT_MS)).subscribe({
      next: (row) => this.battery$.next(row),
      error: () => this.battery$.next(null),
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
