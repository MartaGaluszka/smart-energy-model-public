import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, switchMap, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export interface FoxOverviewResponse {
  day: string;
  pv_kwh: number | null;
  soc_percent: number | null;
  grid_import_kwh: number | null;
  grid_export_kwh: number | null;
  load_kwh: number | null;
  device_sn_display: string;
  last_synced_at: string | null;
  has_data: boolean;
}

export interface FoxSyncResponse {
  status: string;
  start: string | null;
  end: string | null;
  days: number;
  message: string;
}

export interface NotificationDto {
  id: number;
  notif_type: string;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
}

export interface BatteryPolicyResponse {
  title: string;
  body: string;
  automation_enabled: boolean;
  reasons: string[];
}

export interface BatterySuggestionResponse {
  as_of: string;
  season: string;
  season_mode: string;
  soc_now_percent: number | null;
  soc_min_percent: number;
  soc_reserve_percent: number;
  soc_target_percent: number;
  soc_min_evening_percent: number;
  force_charge_night_recommended: boolean;
  force_charge_night_label: string;
  force_charge_afternoon_recommended: boolean;
  force_charge_afternoon_label: string;
  force_charge_night_start?: string | null;
  force_charge_night_end?: string | null;
  force_charge_night_minutes?: number | null;
  force_charge_afternoon_window?: string | null;
  charge_when_summary?: string;
  fc_max_minutes?: number;
  fc_night_start_hour?: number;
  soc16_alert: boolean;
  soc16_hour_passed: boolean;
  soc16_percent: number | null;
  soc16_title: string | null;
  soc16_body: string | null;
  wait_for_cheap: boolean;
  next_cheap_window: string | null;
  recommendation: string;
  action: string;
  automation_enabled: boolean;
  note: string;
}

/** GET/PUT /battery/settings (T4.2 / T4.3). */
export type BatteryScheduleMode = 'ForceCharge' | 'SelfUse' | 'ForceDischarge';

export interface BatteryScheduleWindow {
  start: string;
  end: string;
  mode: BatteryScheduleMode;
  enabled: boolean;
}

export interface BatterySettingsResponse {
  soc_min_percent: number;
  soc_reserve_percent: number;
  soc_target_percent: number;
  efficiency_pct: number;
  price_zone1: number | null;
  price_zone2: number | null;
  season: string;
  season_resolved: string;
  battery_capacity_kwh: number | null;
  ac_power_kw: number | null;
  fc_max_minutes: number;
  fc_night_start_hour: number;
  recommended_fc_max_minutes: number;
  schedule_windows: BatteryScheduleWindow[];
  schedule_max_windows: number;
  schedule_preset: string;
}

export interface BatterySettingsUpdate {
  soc_min_percent: number;
  soc_target_percent: number;
  efficiency_pct: number;
  price_zone1: number | null;
  price_zone2: number | null;
  season: string;
  battery_capacity_kwh: number | null;
  ac_power_kw: number | null;
  fc_max_minutes: number;
  fc_night_start_hour: number;
  schedule_windows: BatteryScheduleWindow[];
  schedule_preset: string;
}

export interface BatteryPlanHour {
  hour: number;
  zone: number;
  zone_label: string;
  force_charge_recommended: boolean;
  planned_soc_percent: number | null;
}

/** GET /battery/plan?date= — plan doradczy 24h (T4.1 / T4.4). */
export interface BatteryPlanResponse {
  date: string;
  season: string;
  hours: BatteryPlanHour[];
  note: string;
}

/** GET /battery/shadow-savings?from=&to= — kontrfakt (T4.15 / T4.16). */
export interface ShadowSavingsResponse {
  period_from: string;
  period_to: string;
  shadow_savings_pln: number;
  baseline_cost_pln: number;
  actual_cost_pln: number;
  method_note: string;
  is_hypothetical: boolean;
}

export interface HourlyForecastResponse {
  day: string;
  hours: {
    hour: number;
    predicted_kwh: number;
    prediction_source: string;
    actual_kwh: number | null;
    error_pct: number | null;
  }[];
  total_kwh: number;
  model_path: string;
}

export interface ForecastValidationHourlyRow {
  run_label: string;
  rank: number;
  predicted_hour: number;
  predicted_kwh: number;
  actual_pv_ml_kwh: number | null;
  actual_report_kwh: number | null;
  error_vs_ml_kwh: number | null;
  /** Błąd % = (predicted - actual) / actual * 100; dodatni = prognoza zawyżona. */
  error_vs_ml_pct: number | null;
}

export interface ForecastValidationDailyRow {
  run_label: string;
  forecast_run_at: string | null;
  predicted_total_kwh: number;
  /** model_raw | hybrid_path | adjusted — skąd suma dnia (outlook) */
  outlook_mode?: string | null;
  /** Wypełnione dopiero gdy ForecastValidationResponse.is_complete=true (dzień zamknięty,
   *  czyli po wieczornej synchronizacji) — dopóki dzień trwa, to i error_* są null. */
  actual_total_kwh: number | null;
  error_kwh: number | null;
  error_pct: number | null;
}

export interface ForecastValidationPeakRow {
  run_label: string;
  predicted_peak_hour: number;
  predicted_peak_kwh: number;
  actual_peak_hour_ml: number | null;
  actual_peak_kwh_ml: number | null;
}

export interface ForecastValidationResponse {
  day: string;
  daily: ForecastValidationDailyRow[];
  hourly: ForecastValidationHourlyRow[];
  peaks: ForecastValidationPeakRow[];
  note: string | null;
  /** false = dzień jeszcze trwa (przed zachodem słońca + margines / wieczorną synchronizacją). */
  is_complete: boolean;
  /** Produkcja dotychczasowa (jak "Dzienna produkcja" w apce FoxESS), tylko gdy is_complete=false. */
  actual_so_far_kwh: number | null;
}

/** Stawki z GET/POST /tariff/rates (T2.1–T2.2). */
export interface TariffRates {
  valid_from: string;
  valid_to: string | null;
  tariff_name: string;
  price_zone1_day: number;
  price_zone2_night: number;
  distribution_zone1: number | null;
  distribution_zone2: number | null;
  subscription_fee_monthly: number | null;
  power_fee_monthly: number | null;
  oze_fee_kwh: number | null;
  vat_mode: string;
  notes: string | null;
  source: string;
}

/** Body zapisu stawek — bez `source` / `valid_to` (backend ich nie wymaga). */
export interface TariffRatesCreate {
  valid_from: string;
  tariff_name: string;
  price_zone1_day: number;
  price_zone2_night: number;
  distribution_zone1: number | null;
  distribution_zone2: number | null;
  subscription_fee_monthly: number | null;
  power_fee_monthly: number | null;
  oze_fee_kwh: number | null;
  vat_mode: string;
  notes: string | null;
}

export interface SimulateBillRequest {
  period_start: string;
  period_end: string;
  rates_override: TariffRatesCreate | null;
}

export interface SimulateBillResponse {
  /** T2.7: netto i brutto (VAT 23% doliczony na końcu, jak kwota "do zapłaty" na fakturze) razem. */
  cost_no_pv_net_pln: number;
  cost_no_pv_gross_pln: number;
  cost_with_pv_net_pln: number;
  cost_with_pv_gross_pln: number;
  savings_net_pln: number;
  savings_gross_pln: number;
  /** T2.6: mini tabela kWh "dach / sieć / oddanie" — produkcja z paneli (dach). */
  production_kwh: number;
  import_kwh: number;
  export_kwh: number;
  self_consumed_kwh: number;
  deposit_credit_pln: number | null;
}

/**
 * Klient HTTP do `api/` (FastAPI, Faza 0) — kontrakt §12 z PROJEKT_APLIKACJA_MOBILNA.md.
 * Wszystkie wywołania czekają na sesję JWT (AuthService.ensureSession) i dołączają
 * nagłówek Authorization automatycznie.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient, private readonly auth: AuthService) {}

  /** Dołącza JWT i, po wygaśnięciu access tokena (401), próbuje raz odświeżyć sesję i powtórzyć wywołanie. */
  private authed<T>(request: (token: string) => Observable<T>): Observable<T> {
    return this.auth.ensureSession().pipe(
      switchMap((token) => request(token ?? '')),
      catchError((err) => {
        if (err instanceof HttpErrorResponse && err.status === 401) {
          return this.auth.renewSession().pipe(switchMap((token) => request(token ?? '')));
        }
        return throwError(() => err);
      }),
    );
  }

  getFoxOverview(day?: string): Observable<FoxOverviewResponse> {
    const query = day ? `?day=${encodeURIComponent(day)}` : '';
    return this.authed((token) =>
      this.http.get<FoxOverviewResponse>(`${this.baseUrl}/api/v1/foxess/overview${query}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  /** Bez argumentów: backend sam liczy brakujący odcinek (od ostatniego zapisanego dnia do dziś). */
  syncFox(start?: string, end?: string): Observable<FoxSyncResponse> {
    return this.authed((token) =>
      this.http.post<FoxSyncResponse>(
        `${this.baseUrl}/api/v1/foxess/sync`,
        { start: start ?? null, end: end ?? null },
        { headers: { Authorization: `Bearer ${token}` } },
      ),
    );
  }

  getNotifications(): Observable<NotificationDto[]> {
    return this.authed((token) =>
      this.http.get<NotificationDto[]>(`${this.baseUrl}/api/v1/notifications`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  getBatteryPolicy(): Observable<BatteryPolicyResponse> {
    return this.authed((token) =>
      this.http.get<BatteryPolicyResponse>(`${this.baseUrl}/api/v1/battery/policy`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  getBatterySuggestion(): Observable<BatterySuggestionResponse> {
    return this.authed((token) =>
      this.http.get<BatterySuggestionResponse>(`${this.baseUrl}/api/v1/battery/suggestion`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  getBatterySettings(): Observable<BatterySettingsResponse> {
    return this.authed((token) =>
      this.http.get<BatterySettingsResponse>(`${this.baseUrl}/api/v1/battery/settings`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  updateBatterySettings(body: BatterySettingsUpdate): Observable<BatterySettingsResponse> {
    return this.authed((token) =>
      this.http.put<BatterySettingsResponse>(`${this.baseUrl}/api/v1/battery/settings`, body, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  getBatteryPlan(date: string): Observable<BatteryPlanResponse> {
    return this.authed((token) =>
      this.http.get<BatteryPlanResponse>(
        `${this.baseUrl}/api/v1/battery/plan?date=${encodeURIComponent(date)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      ),
    );
  }

  getShadowSavings(from: string, to: string): Observable<ShadowSavingsResponse> {
    const q = `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
    return this.authed((token) =>
      this.http.get<ShadowSavingsResponse>(`${this.baseUrl}/api/v1/battery/shadow-savings?${q}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  getForecastHourly(day?: string): Observable<HourlyForecastResponse> {
    const query = day ? `?day=${encodeURIComponent(day)}` : '';
    return this.authed((token) =>
      this.http.get<HourlyForecastResponse>(`${this.baseUrl}/api/v1/forecast/hourly${query}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  getForecastValidation(day: string): Observable<ForecastValidationResponse> {
    return this.authed((token) =>
      this.http.get<ForecastValidationResponse>(
        `${this.baseUrl}/api/v1/forecast/validation?day=${encodeURIComponent(day)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      ),
    );
  }

  getTariffRates(): Observable<TariffRates> {
    return this.authed((token) =>
      this.http.get<TariffRates>(`${this.baseUrl}/api/v1/tariff/rates`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  saveTariffRates(body: TariffRatesCreate): Observable<TariffRates> {
    return this.authed((token) =>
      this.http.post<TariffRates>(`${this.baseUrl}/api/v1/tariff/rates`, body, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  /** Wszystkie zapisane stawki użytkownika (może zmieniać taryfę kilka razy w roku) — najnowsza pierwsza. */
  getTariffRatesHistory(): Observable<TariffRates[]> {
    return this.authed((token) =>
      this.http.get<TariffRates[]>(`${this.baseUrl}/api/v1/tariff/rates/history`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  deleteTariffRates(validFrom: string): Observable<void> {
    return this.authed((token) =>
      this.http.delete<void>(`${this.baseUrl}/api/v1/tariff/rates/${encodeURIComponent(validFrom)}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }

  simulateBill(body: SimulateBillRequest): Observable<SimulateBillResponse> {
    return this.authed((token) =>
      this.http.post<SimulateBillResponse>(`${this.baseUrl}/api/v1/simulate/bill`, body, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    );
  }
}
