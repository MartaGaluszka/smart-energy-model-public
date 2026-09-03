import { Injectable, signal, computed } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { tap } from 'rxjs/operators';
import { ApiService, BatterySettingsResponse, BatterySettingsUpdate } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

/**
 * Single Source of Truth dla stanu baterii.
 * 
 * Używa Angular Signals (16+) do reaktywnego zarządzania stanem
 * współdzielonym między Settings/Schedule/Analytics.
 * 
 * Korzyści:
 * - Eliminuje bug nadpisywania pól między zakładkami
 * - Zachowuje draft przy przełączaniu tabs (bez utraty edycji)
 * - Single API call zamiast 3× (Settings/Schedule/Analytics osobno)
 * - hasUnsavedChanges tracking dla guard/warning
 */
@Injectable({ providedIn: 'root' })
export class BatteryStateService {
  // Private writable signals
  private readonly _state = signal<BatterySettingsResponse | null>(null);
  private readonly _savedSnapshot = signal<BatterySettingsResponse | null>(null);
  private readonly _loading = signal(false);
  private readonly _saving = signal(false);
  private readonly _error = signal<string | null>(null);
  private readonly _saveMessage = signal<string | null>(null);

  // Public readonly signals
  readonly state = this._state.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly saving = this._saving.asReadonly();
  readonly error = this._error.asReadonly();
  readonly saveMessage = this._saveMessage.asReadonly();

  /**
   * Computed signal: deep comparison obecnego stanu z ostatnim zapisanym snapshot.
   * 
   * Używane do:
   * - Disable/enable przycisku "Zapisz"
   * - Ostrzeżenie przed nawigacją (canDeactivate guard)
   * - UI badge "niezapisane zmiany"
   */
  readonly hasUnsavedChanges = computed(() => {
    const current = this._state();
    const saved = this._savedSnapshot();
    
    if (!current || !saved) {
      return false;
    }

    // Deep comparison kluczowych pól (bez pól readonly jak season_resolved)
    return (
      current.soc_min_percent !== saved.soc_min_percent ||
      current.soc_target_percent !== saved.soc_target_percent ||
      current.efficiency_pct !== saved.efficiency_pct ||
      current.battery_capacity_kwh !== saved.battery_capacity_kwh ||
      current.season !== saved.season ||
      current.ac_power_kw !== saved.ac_power_kw ||
      current.fc_max_minutes !== saved.fc_max_minutes ||
      current.fc_night_start_hour !== saved.fc_night_start_hour ||
      JSON.stringify(current.schedule_windows) !== JSON.stringify(saved.schedule_windows) ||
      current.schedule_preset !== saved.schedule_preset ||
      current.price_zone1 !== saved.price_zone1 ||
      current.price_zone2 !== saved.price_zone2
    );
  });

  constructor(
    private readonly api: ApiService,
    private readonly auth: AuthService,
  ) {}

  /**
   * Załaduj ustawienia z API.
   * Wywoływane w BatteryPage.ionViewWillEnter — jeden request współdzielony przez tabs.
   */
  loadSettings(force = false): void {
    if (this._loading() && !force) {
      return;
    }

    if (force) {
      this.auth.logout();
    }

    this._loading.set(true);
    this._error.set(null);

    this.api.getBatterySettings().subscribe({
      next: (row) => {
        this._state.set(row);
        this._savedSnapshot.set(structuredClone(row));
        this._loading.set(false);
      },
      error: (err) => {
        console.warn('[BatteryStateService] GET /battery/settings failed', err);
        this._error.set(
          this.formatHttpError(err, 'GET /api/v1/battery/settings — nieznany błąd'),
        );
        this._loading.set(false);
      },
    });
  }

  /**
   * Aktualizuj częściowy stan (type-safe).
   * 
   * Przykład:
   * ```typescript
   * stateService.updateSettings({ soc_min_percent: 30 });
   * ```
   */
  updateSettings(partial: Partial<BatterySettingsResponse>): void {
    this._state.update((current) => (current ? { ...current, ...partial } : null));
  }

  /**
   * Zapisz cały stan na backend (globalny "Zapisz").
   * 
   * Po sukcesie:
   * - Aktualizuje snapshot (hasUnsavedChanges → false)
   * - Pokazuje komunikat "Zapisano ustawienia"
   */
  saveSettings(options?: { silent?: boolean }): Observable<BatterySettingsResponse> {
    const current = this._state();
    if (!current) {
      return throwError(() => new Error('Brak stanu do zapisania.'));
    }

    this._saving.set(true);
    if (!options?.silent) {
      this._saveMessage.set(null);
    }
    this._error.set(null);

    // Konwersja BatterySettingsResponse → BatterySettingsUpdate
    const body: BatterySettingsUpdate = {
      soc_min_percent: current.soc_min_percent,
      soc_target_percent: current.soc_target_percent,
      efficiency_pct: current.efficiency_pct,
      battery_capacity_kwh: current.battery_capacity_kwh,
      season: current.season,
      ac_power_kw: current.ac_power_kw,
      fc_max_minutes: current.fc_max_minutes,
      fc_night_start_hour: current.fc_night_start_hour,
      schedule_windows: current.schedule_windows,
      schedule_preset: current.schedule_preset,
      price_zone1: current.price_zone1,
      price_zone2: current.price_zone2,
    };

    return this.api.updateBatterySettings(body).pipe(
      tap({
        next: (saved) => {
          this._state.set(saved);
          this._savedSnapshot.set(structuredClone(saved));
          this._saving.set(false);
          if (!options?.silent) {
            this._saveMessage.set('Zapisano ustawienia baterii');
            setTimeout(() => this._saveMessage.set(null), 3000);
          }
        },
        error: (err) => {
          this._saving.set(false);
          this._error.set(
            this.formatHttpError(err, 'PUT /api/v1/battery/settings — nieznany błąd'),
          );
        },
      })
    );
  }

  /** Zapis mocy AC — parametr obciążenia domu, nie baterii (Analytics / Home). */
  persistAcPowerKw(kw: number, options?: { silent?: boolean }): Observable<BatterySettingsResponse> {
    const rounded = Math.round(Number(kw) * 10) / 10;
    this.updateSettings({ ac_power_kw: rounded });
    return this.saveSettings(options);
  }

  /**
   * Wyczyść komunikaty (opcjonalnie, jeśli potrzebujemy manualnie).
   */
  clearMessages(): void {
    this._error.set(null);
    this._saveMessage.set(null);
  }

  /** Pełny komunikat techniczny dla UI (status HTTP, detail z FastAPI, message). */
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
        if (typeof body.code === 'string' && body.code) {
          parts.push(`code=${body.code}`);
        }
        const detail = body.detail;
        if (typeof detail === 'string' && detail.trim()) {
          parts.push(detail.trim());
        } else if (Array.isArray(detail)) {
          parts.push(JSON.stringify(detail));
        } else if (detail != null) {
          parts.push(String(detail));
        }
      }
      if (err.message && !parts.some((p) => p.includes(err.message))) {
        parts.push(err.message);
      }
      if (err.url) {
        parts.push(err.url);
      }
      return parts.length ? parts.join(' · ') : fallback;
    }
    if (err instanceof Error && err.message) {
      return err.message;
    }
    if (typeof err === 'string' && err.trim()) {
      return err.trim();
    }
    return fallback;
  }
}
