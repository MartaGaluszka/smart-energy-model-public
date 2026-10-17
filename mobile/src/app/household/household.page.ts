import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AlertController, ToastController, ViewWillEnter } from '@ionic/angular';
import { addIcons } from 'ionicons';
import {
  addOutline,
  airplaneOutline,
  basketOutline,
  calendarOutline,
  carOutline,
  chevronDownOutline,
  copyOutline,
  constructOutline,
  flashOutline,
  homeOutline,
  laptopOutline,
  leafOutline,
  sunnyOutline,
  thermometerOutline,
  trashOutline,
  waterOutline,
} from 'ionicons/icons';
import { Observable, Subscription, forkJoin, of, timeout } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import {
  ApiService,
  BatterySettingsResponse,
  BatterySuggestionResponse,
  FoxOverviewResponse,
  FloorHeatDayDto,
  HouseholdCustomTypeDto,
  HouseholdEventDto,
} from '../services/api.service';
import { ForecastBridgeService } from '../services/forecast-bridge.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { HOUSEHOLD_CUSTOM_ICONS, isHouseholdCustomIcon } from './household-icons';
import {
  DayEnergyBudget,
  HOUSEHOLD_CUSTOM_ICON_CHOICES,
  HOUSEHOLD_EVENT_TYPES,
  HOUSEHOLD_G12W_SPREAD_PLN,
  HOUSEHOLD_SCENARIOS,
  HouseholdEventTypeDef,
  HouseholdScenario,
  ApplianceWindow,
  bestApplianceWindow,
  buildDayEnergyBudget,
  flexibleDayLine,
  customTypeDef,
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
  readonly customIconChoices = HOUSEHOLD_CUSTOM_ICON_CHOICES;
  /** Tyle znaków mieści się w jednej linii kafelka w siatce 3 kolumn. */
  readonly customLabelMax = 12;
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
  formTypes: string[] = [];
  formError: string | null = null;
  /** Własne pozycje z API — ta sama siatka co katalog. */
  customDefs: HouseholdEventTypeDef[] = [];
  /** Ukryte z siatki, ale nadal opisują dni, które już je mają. */
  private archivedDefs: HouseholdEventTypeDef[] = [];
  showCustomForm = false;
  savingCustom = false;
  customName = '';
  customIcon = 'car-outline';
  customKwh = '';
  customFormError: string | null = null;
  insightBanner: string | null = null;
  /** Porównanie ikon z prognozą dnia i SoC. Nie blokuje widoku tygodnia. */
  focusBudget: DayEnergyBudget | null = null;
  /** Okno godzinowe pod urządzenia z planu, policzone z prognozy. */
  focusWindow: ApplianceWindow | null = null;
  /** Przy słabym dachu: posiłek zostaje, pranie można przełożyć. */
  flexLine: string | null = null;
  budgetLoading = false;
  /** Zmierzone kWh bufora na dzień (Fox), zamiast katalogowego 1,2. */
  private floorHeatByDay: Record<string, number> = {};
  /** kWh cykli od północy do 10:00 — ile grzanie zjadło takiej nocy. */
  private nightHeatByDay: Record<string, number> = {};
  private budgetSub?: Subscription;

  constructor(
    private readonly api: ApiService,
    private readonly alerts: AlertController,
    private readonly toasts: ToastController,
    private readonly router: Router,
    private readonly forecastBridge: ForecastBridgeService,
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
      carOutline,
      copyOutline,
      flashOutline,
      constructOutline,
      homeOutline,
      waterOutline,
      laptopOutline,
      leafOutline,
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
    forkJoin({
      events: this.api.getHouseholdEvents(from, to),
      customs: this.api.getHouseholdCustomTypes().pipe(catchError(() => of([] as HouseholdCustomTypeDto[]))),
      floorHeat: this.api.getFloorHeat(from, to).pipe(catchError(() => of([] as FloorHeatDayDto[]))),
    }).subscribe({
      next: ({ events, customs, floorHeat }) => {
        const rows = customs ?? [];
        this.customDefs = rows.filter((row) => !row.archived).map((row) => customTypeDef(row));
        this.archivedDefs = rows.filter((row) => row.archived).map((row) => customTypeDef(row));
        this.events = events ?? [];
        this.floorHeatByDay = {};
        this.nightHeatByDay = {};
        for (const row of floorHeat ?? []) {
          if (row.kwh > 0) this.floorHeatByDay[row.day] = row.kwh;
          if ((row.night_kwh ?? 0) > 0) this.nightHeatByDay[row.day] = row.night_kwh ?? 0;
        }
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
      this.flexLine = null;
      return;
    }
    const types = day.events.map((e) => e.event_type);
    this.budgetLoading = true;
    this.focusWindow = null;
    this.flexLine = null;
    this.budgetSub?.unsubscribe();
    const limited = <T>(source: Observable<T>) =>
      source.pipe(timeout({ first: 8000 }), catchError(() => of(null as T | null)));
    const useActual = day.isToday;
    this.budgetSub = forkJoin({
      forecast: limited(this.api.getForecastHourly(day.dayIso)),
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
        extraTypes: this.allCustomDefs(),
        floorHeatKwh: this.floorHeatByDay[day.dayIso] ?? null,
        nightHeatKwh: day.isToday ? this.nightHeatByDay[day.dayIso] ?? null : null,
      });
      this.focusWindow = bestApplianceWindow(
        types,
        (forecast?.hours ?? []).map((row) => ({ hour: row.hour, predictedKwh: row.predicted_kwh })),
      );
      const roofKwh = useActual ? actualPv : forecastPv;
      this.flexLine = flexibleDayLine(types, roofKwh);
      this.budgetLoading = false;
    });
  }

  openForecast(): void {
    const day = this.focusDay;
    if (!day) return;
    this.forecastBridge.open(day.dayIso);
    void this.router.navigate(['/tabs/tab3']);
  }

  formatKwh(n: number | null | undefined): string {
    if (n == null || !Number.isFinite(n)) return '—';
    return fmtKwh(n);
  }

  openAdd(dayIso?: string): void {
    this.formDate = dayIso ?? this.focusDayIso ?? todayIsoLocal();
    this.formTypes = this.typesOn(this.formDate);
    this.formError = null;
    this.showCustomForm = false;
    this.showAdd = true;
    this.insightBanner = null;
  }

  closeAdd(): void {
    this.showAdd = false;
    this.showDatePicker = false;
    this.showCustomForm = false;
    this.saving = false;
    this.savingCustom = false;
    this.formError = null;
  }

  isCustomType(value: string): boolean {
    return /^c\d+$/.test(value);
  }

  async confirmRemoveCustom(def: HouseholdEventTypeDef, event: Event): Promise<void> {
    event.stopPropagation();
    event.preventDefault();
    const id = Number(def.value.slice(1));
    const alert = await this.alerts.create({
      header: 'Usunąć własną ikonę?',
      message: `„${def.label}” zniknie z listy. Dni, które już ją mają, zostaną bez zmian.`,
      cssClass: 'se-alert',
      buttons: [
        { text: 'Anuluj', role: 'cancel' },
        {
          text: 'Usuń',
          role: 'destructive',
          handler: () => this.removeCustom(id, def.value),
        },
      ],
    });
    await alert.present();
  }

  private removeCustom(id: number, value: string): void {
    this.api.deleteHouseholdCustomType(id).subscribe({
      next: () => {
        const removed = this.customDefs.find((d) => d.value === value);
        this.customDefs = this.customDefs.filter((d) => d.value !== value);
        if (removed) {
          this.archivedDefs = [...this.archivedDefs, removed];
        }
        this.formTypes = this.formTypes.filter((t) => t !== value);
        this.days = this.buildDays(todayIsoLocal(), this.horizonDays, this.events);
      },
      error: () => {
        this.formError = 'Nie udało się usunąć własnej ikony.';
      },
    });
  }

  private allCustomDefs(): HouseholdEventTypeDef[] {
    return [...this.customDefs, ...this.archivedDefs];
  }

  pickCustomIcon(name: string, event?: Event): void {
    event?.preventDefault();
    this.customIcon = name;
  }

  openCustomForm(): void {
    this.customName = '';
    this.customIcon = 'car-outline';
    this.customKwh = '';
    this.customFormError = null;
    this.showCustomForm = true;
  }

  closeCustomForm(): void {
    this.showCustomForm = false;
    this.savingCustom = false;
    this.customFormError = null;
  }

  saveCustom(): void {
    const label = this.customName.trim().replace(/\s+/g, ' ');
    const kwh = Number(this.customKwh.trim().replace(',', '.'));
    if (!label || label.length > this.customLabelMax) {
      this.customFormError = `Nazwa może mieć najwyżej ${this.customLabelMax} znaków, żeby zmieściła się na kafelku.`;
      return;
    }
    if (!Number.isFinite(kwh) || kwh <= 0 || kwh > 100) {
      this.customFormError = 'Podaj zużycie w kWh, większe od zera i nie większe niż 100.';
      return;
    }
    this.savingCustom = true;
    this.customFormError = null;
    this.api
      .createHouseholdCustomType({ label, icon: this.customIcon, kwh: Math.round(kwh * 100) / 100 })
      .pipe(timeout(15000))
      .subscribe({
        next: (row) => {
          const def = customTypeDef(row);
          this.customDefs = [...this.customDefs, def];
          this.formTypes = [...this.formTypes, def.value];
          this.savingCustom = false;
          this.showCustomForm = false;
        },
        error: (err: unknown) => {
          this.savingCustom = false;
          this.customFormError = this.describeSaveError(err);
        },
      });
  }

  openDatePicker(): void {
    this.showDatePicker = true;
  }

  closeDatePicker(): void {
    this.showDatePicker = false;
  }

  onFormDate(value: string | string[] | null): void {
    const next = toDateOnly(value) || this.formDate;
    if (next === this.formDate) return;
    this.formDate = next;
    this.formTypes = this.typesOn(next);
  }

  pickScenario(s: HouseholdScenario): void {
    this.formTypes = [...s.eventTypes];
  }

  /** Kafelki z dnia poprzedzającego datę w arkuszu. */
  get previousDayTypes(): string[] {
    if (!this.formDate) return [];
    const prev = shiftIsoDate(this.formDate, -1);
    return this.events.filter((event) => event.event_date === prev).map((event) => event.event_type);
  }

  get previousDayLabel(): string {
    return this.formDate === todayIsoLocal() ? 'Jak wczoraj' : 'Jak dzień wcześniej';
  }

  pickPreviousDay(): void {
    const types = this.previousDayTypes;
    if (!types.length) return;
    this.formTypes = [...types];
  }

  isPreviousDayActive(): boolean {
    const types = this.previousDayTypes;
    if (!types.length || types.length !== this.formTypes.length) return false;
    return types.every((type) => this.formTypes.includes(type));
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

  get plannerTypes(): HouseholdEventTypeDef[] {
    return [...this.typeCatalog, ...this.customDefs];
  }

  get selectedDefs(): HouseholdEventTypeDef[] {
    return this.formTypes
      .map((t) => this.defFor(t))
      .filter((d): d is HouseholdEventTypeDef => !!d);
  }

  get saveLabel(): string {
    if (this.saving) return 'Zapisuję…';
    const n = this.formTypes.length;
    if (n <= 1) return 'Zapisz';
    return `Zapisz (${n})`;
  }

  /** Arkusz różni się od kafelków już zapisanych na ten dzień. */
  get planChanged(): boolean {
    const current = this.typesOn(this.formDate);
    if (current.length !== this.formTypes.length) return true;
    const left = [...current];
    for (const type of this.formTypes) {
      const idx = left.indexOf(type);
      if (idx < 0) return true;
      left.splice(idx, 1);
    }
    return false;
  }

  private typesOn(dayIso: string): string[] {
    if (!dayIso) return [];
    return this.events.filter((event) => event.event_date === dayIso).map((event) => event.event_type);
  }

  get selectedLabelsSummary(): string {
    return this.selectedDefs.map((d) => d.label).join(' · ');
  }

  private defFor(type: string): HouseholdEventTypeDef | undefined {
    return (
      this.customDefs.find((d) => d.value === type) ??
      this.archivedDefs.find((d) => d.value === type) ??
      eventTypeDef(type)
    );
  }

  typeDef(type: string): HouseholdEventTypeDef | undefined {
    return this.defFor(type);
  }

  typeLabel(type: string): string {
    return this.defFor(type)?.label ?? type;
  }

  typeIcon(type: string): string {
    return this.defFor(type)?.icon ?? 'calendar-outline';
  }

  /** Własne SVG → data-URL na [src]; ionicons → name. */
  iconSrc(icon: string): string | null {
    return isHouseholdCustomIcon(icon) ? HOUSEHOLD_CUSTOM_ICONS[icon] : null;
  }

  typeTint(type: string): string {
    return this.defFor(type)?.tint ?? 'muted';
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
    if (!this.formDate || this.saving || !this.planChanged) return;
    const pool = this.events
      .filter((event) => event.event_date === this.formDate)
      .map((event) => ({ id: event.id, type: event.event_type, used: false }));
    const toCreate: HouseholdEventTypeDef[] = [];
    for (const type of this.formTypes) {
      const slot = pool.find((row) => !row.used && row.type === type);
      if (slot) {
        slot.used = true;
        continue;
      }
      const def = this.defFor(type);
      if (def) toCreate.push(def);
    }
    const toDelete = pool.filter((row) => !row.used).map((row) => row.id);
    if (!toCreate.length && !toDelete.length) return;
    this.saving = true;
    this.formError = null;
    this.error = null;
    let lastErr = 'Nie udało się zapisać — sprawdź, czy API działa na Macu.';
    const calls: Observable<HouseholdEventDto | null>[] = [
      ...toCreate.map((def) =>
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
      ),
      ...toDelete.map((id) =>
        this.api.deleteHouseholdEvent(id).pipe(
          timeout(15000),
          map(() => ({ id } as HouseholdEventDto)),
          catchError((err: unknown) => {
            lastErr = this.describeSaveError(err);
            return of(null);
          }),
        ),
      ),
    ];
    forkJoin(calls).subscribe({
      next: (rows) => {
        this.saving = false;
        const createdOk = (rows.slice(0, toCreate.length) as Array<HouseholdEventDto | null>).filter(
          (row): row is HouseholdEventDto => row != null,
        );
        const failed = rows.some((row) => row == null);
        if (!createdOk.length && toCreate.length && failed) {
          this.formError = lastErr;
          return;
        }
        if (failed && !createdOk.length && !toDelete.length) {
          this.formError = lastErr;
          return;
        }
        this.showAdd = false;
        this.focusDayIso = this.formDate;
        this.insightBanner = createdOk.length
          ? this.buildInsightMulti(toCreate.slice(0, createdOk.length))
          : null;
        if (failed) {
          this.error = 'Część planu nie przeszła — sprawdź API.';
        }
        const saved = createdOk.length + toDelete.filter((_, index) => rows[toCreate.length + index] != null).length;
        void this.presentToast(saved === 1 ? 'Zapisano plan' : `Zapisano plan (${saved})`);
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
      const pln = this.plnFor(def);
      const money =
        pln != null
          ? ` Szacowany koszt: ok. ${pln.toFixed(2).replace('.', ',')} zł.`
          : '';
      return `Dzięki zaznaczeniu „${def.label}”: ${def.insightHint}${money}`;
    }
    const labels = defs.map((d) => d.label).join(', ');
    let plnSum = 0;
    let any = false;
    for (const d of defs) {
      const p = this.plnFor(d);
      if (p != null) {
        plnSum += p;
        any = true;
      }
    }
    const money = any
      ? ` Szacowany koszt łącznie: ok. ${plnSum.toFixed(2).replace('.', ',')} zł.`
      : '';
    return `Dzięki zaznaczeniu: ${labels}. ${dayAdvisorLine(defs.map((d) => d.value), this.allCustomDefs())}${money}`;
  }

  private plnFor(def: HouseholdEventTypeDef): number | null {
    const known = estimateInsightPln(def.value);
    if (known != null) return known;
    if (def.estimatedKwh <= 0) return null;
    return Math.round(def.estimatedKwh * HOUSEHOLD_G12W_SPREAD_PLN * 100) / 100;
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
        advisorLine: dayAdvisorLine(dayEvents.map((e) => e.event_type), this.allCustomDefs()),
      });
    }
    return out;
  }
}
