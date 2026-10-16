import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { AlertController, ToastController, ViewWillEnter } from '@ionic/angular';
import { addIcons } from 'ionicons';
import {
  addOutline,
  airplaneOutline,
  basketOutline,
  calendarOutline,
  chevronDownOutline,
  sunnyOutline,
  thermometerOutline,
  trashOutline,
} from 'ionicons/icons';
import { Observable, Subscription, forkJoin, of, timeout } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  ApiService,
  BatterySettingsResponse,
  BatterySuggestionResponse,
  FoxOverviewResponse,
  HouseholdEventDto,
} from '../services/api.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { HOUSEHOLD_CUSTOM_ICONS, isHouseholdCustomIcon } from './household-icons';
import {
  DayEnergyBudget,
  HOUSEHOLD_EVENT_TYPES,
  HOUSEHOLD_SCENARIOS,
  HouseholdEventTypeDef,
  HouseholdScenario,
  buildDayEnergyBudget,
  dayAdvisorLine,
  estimateInsightPln,
  eventTypeDef,
  fmtKwh,
  isStackableEventType,
} from './household.types';

/** Jak ROI / Symulator — `ion-datetime` oddaje ISO z czasem. */
function toDateOnly(value: string | string[] | null | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw) return '';
  return String(raw).slice(0, 10);
}

export interface DayBucket {
  dayIso: string;
  label: string;
  weekday: string;
  weekdayShort: string;
  dayNum: string;
  isToday: boolean;
  events: HouseholdEventDto[];
  advisorLine: string;
}

@Component({
  selector: 'app-household',
  templateUrl: './household.page.html',
  styleUrls: ['./household.page.scss'],
  standalone: false,
})
export class HouseholdPage implements OnInit, ViewWillEnter {
  readonly typeCatalog = HOUSEHOLD_EVENT_TYPES;
  readonly scenarios = HOUSEHOLD_SCENARIOS;
  /** Stały horyzont jak pasek Home — 7 dni. */
  readonly horizonDays = 7;

  loading = true;
  error: string | null = null;
  days: DayBucket[] = [];
  events: HouseholdEventDto[] = [];
  /** Wybrany dzień na osi (domyślnie dziś). */
  focusDayIso = todayIsoLocal();

  showAdd = false;
  showDatePicker = false;
  saving = false;
  formDate = todayIsoLocal();
  /** Multi-select typów na jeden dzień. */
  formTypes: string[] = ['pranie'];
  formError: string | null = null;
  insightBanner: string | null = null;
  /** Porównanie ikon z prognozą dnia i SoC. Nie blokuje widoku tygodnia. */
  focusBudget: DayEnergyBudget | null = null;
  budgetLoading = false;
  private budgetSub?: Subscription;

  constructor(
    private readonly api: ApiService,
    private readonly alerts: AlertController,
    private readonly toasts: ToastController,
  ) {
    addIcons({
      calendarOutline,
      addOutline,
      trashOutline,
      thermometerOutline,
      basketOutline,
      airplaneOutline,
      sunnyOutline,
      chevronDownOutline,
    });
  }

  get focusDay(): DayBucket | null {
    return this.days.find((d) => d.dayIso === this.focusDayIso) ?? this.days[0] ?? null;
  }

  get timelineDays(): DayBucket[] {
    return this.days.filter((d) => d.dayIso !== this.focusDayIso);
  }

  ngOnInit(): void {
    this.reload();
  }

  ionViewWillEnter(): void {
    this.reload();
  }

  selectDay(dayIso: string): void {
    this.focusDayIso = dayIso;
    this.insightBanner = null;
    this.refreshFocusBudget();
  }

  reload(): void {
    this.loading = true;
    this.error = null;
    const from = todayIsoLocal();
    if (!this.focusDayIso) {
      this.focusDayIso = from;
    }
    const to = shiftIsoDate(from, this.horizonDays - 1);
    this.api.getHouseholdEvents(from, to).subscribe({
      next: (rows) => {
        this.events = rows ?? [];
        this.days = this.buildDays(from, this.horizonDays, this.events);
        if (!this.days.some((d) => d.dayIso === this.focusDayIso)) {
          this.focusDayIso = from;
        }
        this.loading = false;
        this.refreshFocusBudget();
      },
      error: () => {
        this.loading = false;
        this.error = 'Nie udało się pobrać wydarzeń. Sprawdź API.';
        this.days = this.buildDays(from, this.horizonDays, []);
        this.focusBudget = null;
      },
    });
  }

  /** Prognoza wybranego dnia + SoC. Osobno od listy ikon, z limitem czasu. */
  refreshFocusBudget(): void {
    const day = this.focusDay;
    if (!day) {
      this.focusBudget = null;
      return;
    }
    const types = day.events.map((e) => e.event_type);
    this.budgetLoading = true;
    this.budgetSub?.unsubscribe();
    const limited = <T>(source: Observable<T>) =>
      source.pipe(timeout({ first: 8000 }), catchError(() => of(null as T | null)));
    const useActual = day.isToday;
    this.budgetSub = forkJoin({
      forecast: useActual ? of(null) : limited(this.api.getForecastHourly(day.dayIso)),
      fox: limited(this.api.getFoxOverview(useActual ? day.dayIso : undefined)),
      settings: limited(this.api.getBatterySettings()),
      suggestion: limited(this.api.getBatterySuggestion()),
    }).subscribe(({ forecast, fox, settings, suggestion }) => {
      const forecastPv =
        forecast?.total_kwh != null
          ? forecast.total_kwh
          : forecast?.hours?.length
            ? forecast.hours.reduce((s, h) => s + (h.predicted_kwh || 0), 0)
            : null;
      const foxRow = fox as FoxOverviewResponse | null;
      const settingsRow = settings as BatterySettingsResponse | null;
      const suggestionRow = suggestion as BatterySuggestionResponse | null;
      const actualPv = foxRow?.has_data ? foxRow.pv_kwh : null;
      this.focusBudget = buildDayEnergyBudget({
        eventTypes: types,
        pvKwh: useActual ? actualPv : forecastPv,
        pvSource: useActual ? 'actual' : 'forecast',
        socPercent: foxRow?.soc_percent ?? suggestionRow?.soc_now_percent ?? null,
        capacityKwh: settingsRow?.battery_capacity_kwh ?? null,
        reservePercent: settingsRow?.soc_reserve_percent ?? suggestionRow?.soc_reserve_percent ?? 20,
      });
      this.budgetLoading = false;
    });
  }

  formatKwh(n: number | null | undefined): string {
    if (n == null || !Number.isFinite(n)) return '—';
    return fmtKwh(n);
  }

  openAdd(dayIso?: string): void {
    this.formDate = dayIso ?? this.focusDayIso ?? todayIsoLocal();
    this.formTypes = ['pranie'];
    this.formError = null;
    this.showAdd = true;
    this.insightBanner = null;
  }

  closeAdd(): void {
    this.showAdd = false;
    this.showDatePicker = false;
    this.saving = false;
    this.formError = null;
  }

  openDatePicker(): void {
    this.showDatePicker = true;
  }

  closeDatePicker(): void {
    this.showDatePicker = false;
  }

  onFormDate(value: string | string[] | null): void {
    this.formDate = toDateOnly(value) || this.formDate;
  }

  pickScenario(s: HouseholdScenario): void {
    this.formTypes = [...s.eventTypes];
  }

  isTypeSelected(type: string): boolean {
    return this.countOfType(type) > 0;
  }

  countOfType(type: string): number {
    return this.formTypes.filter((t) => t === type).length;
  }

  isScenarioActive(s: HouseholdScenario): boolean {
    if (!s.eventTypes.length || s.eventTypes.length !== this.formTypes.length) {
      return false;
    }
    return s.eventTypes.every((t) => this.formTypes.includes(t));
  }

  toggleType(type: string): void {
    // Każdy typ: kolejne kliknięcie = kolejny wpis (nie odznaczanie).
    this.formTypes = [...this.formTypes, type];
  }

  isStackable(_type: string): boolean {
    return true;
  }

  /** Zmniejsz liczbę wpisów (chip −). */
  removeOneType(type: string, event?: Event): void {
    event?.stopPropagation();
    const idx = this.formTypes.lastIndexOf(type);
    if (idx < 0) return;
    this.formTypes = [...this.formTypes.slice(0, idx), ...this.formTypes.slice(idx + 1)];
  }

  get selectedDefs(): HouseholdEventTypeDef[] {
    return this.formTypes
      .map((t) => eventTypeDef(t))
      .filter((d): d is HouseholdEventTypeDef => !!d);
  }

  get saveLabel(): string {
    if (this.saving) return 'Zapisuję…';
    const n = this.formTypes.length;
    if (n <= 1) return 'Zapisz';
    return `Zapisz (${n})`;
  }

  get selectedLabelsSummary(): string {
    return this.selectedDefs.map((d) => d.label).join(' · ');
  }

  typeDef(type: string): HouseholdEventTypeDef | undefined {
    return eventTypeDef(type);
  }

  typeLabel(type: string): string {
    return eventTypeDef(type)?.label ?? type;
  }

  typeIcon(type: string): string {
    return eventTypeDef(type)?.icon ?? 'calendar-outline';
  }

  /** Własne SVG → data-URL na [src]; ionicons → name. */
  iconSrc(icon: string): string | null {
    return isHouseholdCustomIcon(icon) ? HOUSEHOLD_CUSTOM_ICONS[icon] : null;
  }

  typeTint(type: string): string {
    return eventTypeDef(type)?.tint ?? 'muted';
  }

  eventSummary(day: DayBucket): string {
    if (!day.events.length) return '—';
    const counts = new Map<string, number>();
    for (const e of day.events) {
      counts.set(e.event_type, (counts.get(e.event_type) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([type, n]) => (n > 1 ? `${this.typeLabel(type)} ×${n}` : this.typeLabel(type)))
      .join(' · ');
  }

  /** Etykieta chipa w bohaterze — z ×n gdy kilka cykli tego samego typu pod rząd. */
  chipLabel(ev: HouseholdEventDto, dayEvents: HouseholdEventDto[]): string {
    const same = dayEvents.filter((e) => e.event_type === ev.event_type);
    if (same.length <= 1) return this.typeLabel(ev.event_type);
    const ord = same.findIndex((e) => e.id === ev.id) + 1;
    return `${this.typeLabel(ev.event_type)} (${ord}/${same.length})`;
  }

  save(): void {
    const defs = this.selectedDefs;
    if (!defs.length || !this.formDate || this.saving) return;
    this.saving = true;
    this.formError = null;
    this.error = null;
    let lastErr = 'Nie udało się zapisać — sprawdź, czy API działa na Macu.';
    const calls = defs.map((def) =>
      this.api
        .createHouseholdEvent({
          event_date: this.formDate,
          event_type: def.value,
          impact: def.defaultImpact,
        })
        .pipe(
          timeout(15000),
          catchError((err: unknown) => {
            lastErr = this.describeSaveError(err);
            return of(null);
          }),
        ),
    );
    forkJoin(calls).subscribe({
      next: (rows) => {
        this.saving = false;
        const ok = (rows as Array<HouseholdEventDto | null>).filter(
          (r): r is HouseholdEventDto => r != null,
        );
        if (!ok.length) {
          this.formError = lastErr;
          return;
        }
        this.showAdd = false;
        this.focusDayIso = this.formDate;
        this.insightBanner = this.buildInsightMulti(defs.slice(0, ok.length));
        if (ok.length < defs.length) {
          this.error = `Zapisano ${ok.length} z ${defs.length} — część nie przeszła (API).`;
        }
        void this.presentToast(
          ok.length === defs.length
            ? `Zapisano ${ok.length} plan${ok.length === 1 ? '' : 'y'}`
            : `Zapisano ${ok.length} z ${defs.length}`,
        );
        this.reload();
      },
      error: (err: unknown) => {
        this.saving = false;
        this.formError = this.describeSaveError(err);
      },
    });
  }

  private describeSaveError(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 0) {
        return 'Brak połączenia z API (Simulator → Mac:8000). Uruchom API i spróbuj ponownie.';
      }
      if (err.status === 401 || err.status === 403) {
        return 'Sesja wygasła — zamknij i otwórz ekran ponownie.';
      }
      const detail = (err.error as { detail?: unknown } | null)?.detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
      return `API odmówiło zapisu (HTTP ${err.status}).`;
    }
    if (err && typeof err === 'object' && 'name' in err && (err as { name: string }).name === 'TimeoutError') {
      return 'API nie odpowiada (timeout). Sprawdź, czy backend działa.';
    }
    return 'Nie udało się zapisać wydarzeń.';
  }

  private async presentToast(message: string): Promise<void> {
    const toast = await this.toasts.create({
      message,
      duration: 2200,
      position: 'bottom',
      color: 'dark',
    });
    await toast.present();
  }

  async confirmDelete(ev: HouseholdEventDto): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Usunąć wydarzenie?',
      message: `${this.typeLabel(ev.event_type)} · ${ev.event_date}`,
      cssClass: 'se-alert',
      buttons: [
        { text: 'Anuluj', role: 'cancel' },
        {
          text: 'Usuń',
          role: 'destructive',
          handler: () => this.delete(ev.id),
        },
      ],
    });
    await alert.present();
  }

  private delete(id: number): void {
    this.api.deleteHouseholdEvent(id).subscribe({
      next: () => this.reload(),
      error: () => {
        this.error = 'Nie udało się usunąć wydarzenia.';
      },
    });
  }

  private buildInsightMulti(defs: HouseholdEventTypeDef[]): string {
    if (defs.length === 1) {
      const def = defs[0];
      const pln = estimateInsightPln(def.value);
      const money =
        pln != null
          ? ` Szacunek: ok. ${pln.toFixed(2).replace('.', ',')} zł (spread G12w).`
          : '';
      return `Dzięki zaznaczeniu „${def.label}”: ${def.insightHint}${money}`;
    }
    const labels = defs.map((d) => d.label).join(', ');
    let plnSum = 0;
    let any = false;
    for (const d of defs) {
      const p = estimateInsightPln(d.value);
      if (p != null) {
        plnSum += p;
        any = true;
      }
    }
    const money = any
      ? ` Szacunek łącznie: ok. ${plnSum.toFixed(2).replace('.', ',')} zł (spread G12w).`
      : '';
    return `Dzięki zaznaczeniu: ${labels}. ${dayAdvisorLine(defs.map((d) => d.value))}${money}`;
  }

  private buildDays(
    fromIso: string,
    count: number,
    events: HouseholdEventDto[],
  ): DayBucket[] {
    const today = todayIsoLocal();
    const byDay = new Map<string, HouseholdEventDto[]>();
    for (const e of events) {
      const list = byDay.get(e.event_date) ?? [];
      list.push(e);
      byDay.set(e.event_date, list);
    }
    const out: DayBucket[] = [];
    for (let i = 0; i < count; i++) {
      const dayIso = shiftIsoDate(fromIso, i);
      const d = new Date(`${dayIso}T12:00:00`);
      const dayEvents = byDay.get(dayIso) ?? [];
      out.push({
        dayIso,
        label: d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }),
        weekday: d.toLocaleDateString('pl-PL', { weekday: 'long' }),
        weekdayShort: d.toLocaleDateString('pl-PL', { weekday: 'short' }),
        dayNum: d.toLocaleDateString('pl-PL', { day: 'numeric' }),
        isToday: dayIso === today,
        events: dayEvents,
        advisorLine: dayAdvisorLine(dayEvents.map((e) => e.event_type)),
      });
    }
    return out;
  }
}
