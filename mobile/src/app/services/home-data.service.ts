import { HttpErrorResponse } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, catchError, map, of, switchMap, tap, timeout } from 'rxjs';
import { ApiService, BatterySuggestionResponse, FoxOverviewResponse, NotificationDto } from './api.service';
import { AuthService } from './auth.service';
import { toLocalIsoDate } from '../utils/date-utils';

export interface HomeKpi {
  productionKwh: number | null;
  socPercent: number | null;
  gridImportKwh: number | null;
  gridExportKwh: number | null;
}

export interface Suggestion {
  id: string;
  kind: string;
  title: string;
  body: string;
}

const WINDOW_IN_TITLE = /(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2})/;

/** Jedna karta na typ i na to samo okno godzinowe — nowsza predykcja nadpisuje starszą. */
export function dedupeSuggestions(rows: NotificationDto[]): NotificationDto[] {
  const unread = rows
    .filter((r) => r.read_at === null)
    .slice()
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  const seenType = new Set<string>();
  const seenWindow = new Set<string>();
  const out: NotificationDto[] = [];
  for (const row of unread) {
    const match = WINDOW_IN_TITLE.exec(row.title);
    const windowKey = match ? match[1].replace(/\s/g, '') : null;
    if (windowKey) {
      if (seenWindow.has(windowKey)) continue;
      seenWindow.add(windowKey);
    }
    if (seenType.has(row.notif_type)) continue;
    seenType.add(row.notif_type);
    out.push(row);
  }
  return out;
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
  /** T1.10: true gdy FoxESS zwrócił limit 40402 (albo timeout syncu, zwykle ten sam limit). */
  rateLimited: boolean;
  /** Pełny komunikat techniczny gdy API niedostępne (bez danych demo). */
  apiError: string | null;
}

const FOX_RATE_LIMIT_MSG =
  'Limit API FoxESS (40402). Odczekaj 30–60 min i spróbuj ponownie.';

/** Backend: 429 + code FOXESS_RATE_LIMIT; fallback na treść 40402 (np. stary 502). */
function foxRateLimitMessage(err: unknown): string | null {
  if (!(err instanceof HttpErrorResponse)) {
    return null;
  }
  const body = err.error as { code?: string; detail?: unknown } | null;
  const detail = typeof body?.detail === 'string' ? body.detail : '';
  if (body?.code === 'FOXESS_RATE_LIMIT' || err.status === 429 || detail.includes('40402')) {
    return detail || FOX_RATE_LIMIT_MSG;
  }
  return null;
}

const SYNC_TIMEOUT_MS = 15_000;
const OVERVIEW_TIMEOUT_MS = 10_000;
const LOOKBACK_DAYS = 5;

/**
 * Most między UI (Home / tab1) i `api/` (FastAPI, Faza 0 — patrz §12 dok. projektowego).
 * Brak danych demo — gdy API niedostępne, KPI/bateria = null i `offline` + `apiError`.
 */
@Injectable({ providedIn: 'root' })
export class HomeDataService {
  private readonly kpi$ = new BehaviorSubject<HomeKpi | null>(null);
  private readonly battery$ = new BehaviorSubject<BatterySuggestionResponse | null>(null);
  private readonly sync$ = new BehaviorSubject<SyncStatus>({
    lastSyncedAt: null,
    syncing: false,
    offline: false,
    dataDay: null,
    message: null,
    messageKind: null,
    rateLimited: false,
    apiError: null,
  });

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
  ) {
    this.refreshAll();
  }

  /** Odśwież KPI + sugestię baterii z API (np. przy wejściu na Home). */
  refreshAll(clearSession = false): void {
    if (clearSession) {
      this.auth.logout();
    }
    this.refreshOverview();
    this.refreshBatterySuggestion();
  }

  getKpi(): Observable<HomeKpi | null> {
    return this.kpi$.asObservable();
  }

  getSyncStatus(): Observable<SyncStatus> {
    return this.sync$.asObservable();
  }

  getSuggestions(): Observable<Suggestion[]> {
    return this.api.getNotifications().pipe(
      map((rows) => dedupeSuggestions(rows).map((row) => this.toSuggestion(row))),
      catchError(() => of([] as Suggestion[])),
    );
  }

  getBatterySuggestion(): Observable<BatterySuggestionResponse | null> {
    return this.battery$.asObservable();
  }

  refreshBatterySuggestion(): void {
    // Wyczyść stary snapshot (np. TRYB ZIMOWY), żeby UI nie trzymał cache przy błędzie auth
    this.battery$.next(null);
    this.api.getBatterySuggestion().pipe(timeout(OVERVIEW_TIMEOUT_MS)).subscribe({
      next: (row) => {
        this.battery$.next(row);
      },
      error: (err) => {
        console.warn('[HomeDataService] GET /battery/suggestion failed', err);
        this.battery$.next(null);
      },
    });
  }

  /**
   * Odpowiada `POST /api/v1/foxess/sync` (TA.3) — bez zakresu dat: backend sam dobiera
   * brakujący odcinek (od ostatniego zapisanego dnia do dziś) i pomija wywołanie FoxESS,
   * jeśli dane są już aktualne (cooldown po stronie API) — patrz `foxess_sync.sync_incremental`.
   */
  triggerSync(): Observable<SyncStatus> {
    this.sync$.next({
      ...this.sync$.value,
      syncing: true,
      message: null,
      messageKind: null,
      rateLimited: false,
    });
    return this.api.syncFox().pipe(
      timeout(SYNC_TIMEOUT_MS),
      tap((res) => {
        const skipped = res.status === 'skipped';
        const limited = skipped && (res.message ?? '').includes('40402');
        this.refreshOverview(
          skipped ? res.message : null,
          skipped ? 'info' : null,
          limited,
        );
      }),
      catchError((err) => {
        const timedOut = err?.name === 'TimeoutError';
        const rateLimitMsg = foxRateLimitMessage(err);
        const rateLimited = timedOut || rateLimitMsg !== null;
        this.sync$.next({
          ...this.sync$.value,
          syncing: false,
          message: rateLimitMsg
            ?? (timedOut
              ? 'Synchronizacja z FoxESS trwa długo — możliwy limit API (40402). Spróbuj ponownie za 30–60 min.'
              : 'Synchronizacja nie powiodła się. Sprawdź połączenie z API.'),
          messageKind: 'error',
          rateLimited,
        });
        return of(null);
      }),
      map(() => this.sync$.value),
    );
  }

  private refreshOverview(
    message: string | null = null,
    messageKind: 'error' | 'info' | null = null,
    rateLimited = false,
  ): void {
    this.sync$.next({ ...this.sync$.value, syncing: true, apiError: null });
    this.fetchLatestAvailableOverview(0).subscribe({
      next: (overview) => {
        if (!overview || !overview.has_data) {
          this.kpi$.next(null);
          this.sync$.next({
            ...this.sync$.value,
            syncing: false,
            offline: true,
            apiError: 'GET /api/v1/foxess/overview — brak danych FoxESS w bazie',
          });
          return;
        }
        this.kpi$.next({
          productionKwh: overview.pv_kwh,
          socPercent: overview.soc_percent,
          gridImportKwh: overview.grid_import_kwh,
          gridExportKwh: overview.grid_export_kwh,
        });
        this.sync$.next({
          lastSyncedAt: overview.last_synced_at ? new Date(overview.last_synced_at) : null,
          syncing: false,
          offline: false,
          dataDay: overview.day,
          message,
          messageKind,
          rateLimited,
          apiError: null,
        });
        this.refreshBatterySuggestion();
      },
      error: (err) => {
        console.warn('[HomeDataService] api/foxess/overview niedostępne', err);
        this.kpi$.next(null);
        this.markApiError(err, 'GET /api/v1/foxess/overview — nieznany błąd');
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
    const body = row.body
      .replace(/\s*Sugestia doradcza, bez automatyki\.?/gi, '')
      .replace(/\s*System tylko doradza[^.]*\./gi, '')
      .trim();
    return { id: String(row.id), kind: row.notif_type, title: row.title, body };
  }

  private markApiError(err: unknown, fallback: string): void {
    this.sync$.next({
      ...this.sync$.value,
      offline: true,
      apiError: this.formatHttpError(err, fallback),
    });
  }

  private formatHttpError(err: unknown, fallback: string): string {
    if (err instanceof HttpErrorResponse) {
      const parts: string[] = [];
      if (err.status) {
        parts.push(`HTTP ${err.status}${err.statusText ? ` ${err.statusText}` : ''}`);
      }
      const body = err.error as { code?: string; detail?: unknown } | string | null;
      if (typeof body === 'string' && body.trim()) {
        parts.push(body.trim());
      } else if (body && typeof body === 'object') {
        if (typeof body.code === 'string' && body.code) parts.push(`code=${body.code}`);
        const detail = body.detail;
        if (typeof detail === 'string' && detail.trim()) parts.push(detail.trim());
        else if (detail != null) parts.push(String(detail));
      }
      if (err.message && !parts.some((p) => p.includes(err.message))) parts.push(err.message);
      if (err.url) parts.push(err.url);
      return parts.length ? parts.join(' · ') : fallback;
    }
    if (err instanceof Error && err.message) return err.message;
    if (typeof err === 'string' && err.trim()) return err.trim();
    return fallback;
  }
}
