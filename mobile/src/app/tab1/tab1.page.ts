import { Component, OnDestroy, OnInit } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { BehaviorSubject, Observable, Subscription } from 'rxjs';
import { ApiService, AcRuntimeResponse, BatterySuggestionResponse } from '../services/api.service';
import { HomeDataService, HomeKpi, SyncStatus, Suggestion } from '../services/home-data.service';
import { todayIsoLocal } from '../utils/date-utils';

@Component({
  selector: 'app-tab1',
  templateUrl: 'tab1.page.html',
  styleUrls: ['tab1.page.scss'],
  standalone: false,
})
export class Tab1Page implements OnInit, OnDestroy, ViewWillEnter {
  kpi$!: Observable<HomeKpi>;
  sync$!: Observable<SyncStatus>;
  suggestions$!: Observable<Suggestion[]>;
  battery$!: Observable<BatterySuggestionResponse | null>;
  /** BAT.5: próg koloru SoC = rezerwa sezonowa (lato 20 / zima 40). */
  socReserve = 20;
  /** T4.16: skrót shadow miesiąc (pełna karta na /tabs/battery). */
  shadowMonthPln: number | null = null;
  shadowLoading = false;
  acRuntime: AcRuntimeResponse | null = null;
  private acSub?: Subscription;
  private batterySub?: Subscription;
  private shadowSub?: Subscription;
  private suggestionsSub?: Subscription;
  private readonly suggestionsSubject = new BehaviorSubject<Suggestion[]>([]);

  constructor(
    private readonly homeData: HomeDataService,
    private readonly api: ApiService,
  ) {}

  ngOnInit() {
    this.kpi$ = this.homeData.getKpi();
    this.sync$ = this.homeData.getSyncStatus();
    this.suggestions$ = this.suggestionsSubject.asObservable();
    this.battery$ = this.homeData.getBatterySuggestion();
    this.batterySub = this.battery$.subscribe((row) => {
      this.socReserve = row?.soc_reserve_percent ?? 20;
    });
    this.reloadSuggestions();
  }

  ngOnDestroy() {
    this.batterySub?.unsubscribe();
    this.shadowSub?.unsubscribe();
    this.suggestionsSub?.unsubscribe();
    this.acSub?.unsubscribe();
  }

  ionViewWillEnter() {
    this.homeData.refreshBatterySuggestion();
    this.reloadShadowMonth();
    this.reloadSuggestions();
    this.reloadAc();
  }

  formatPln(value: number | null): string {
    if (value === null || Number.isNaN(value)) return '—';
    return `${value.toFixed(2).replace('.', ',')} zł`;
  }

  private reloadShadowMonth(): void {
    const to = todayIsoLocal();
    const [y, m] = to.split('-');
    const from = `${y}-${m}-01`;
    this.shadowLoading = true;
    this.shadowSub?.unsubscribe();
    this.shadowSub = this.api.getShadowSavings(from, to).subscribe({
      next: (row) => {
        this.shadowMonthPln = row.shadow_savings_pln;
        this.shadowLoading = false;
      },
      error: () => {
        this.shadowMonthPln = null;
        this.shadowLoading = false;
      },
    });
  }

  private reloadAc(): void {
    this.acSub?.unsubscribe();
    this.acSub = this.api.getAcRuntime().subscribe({
      next: (row) => {
        this.acRuntime = row.show_card ? row : null;
      },
      error: () => {
        this.acRuntime = null;
      },
    });
  }

  private reloadSuggestions(): void {
    this.suggestionsSub?.unsubscribe();
    this.suggestionsSub = this.homeData.getSuggestions().subscribe({
      next: (rows) => this.suggestionsSubject.next(rows),
      error: () => this.suggestionsSubject.next([]),
    });
  }

  onSync() {
    this.homeData.triggerSync().subscribe();
  }

  socColor(soc: number, reserve: number = 20): string {
    if (soc >= 50) return 'moss';
    if (soc >= reserve) return 'warning';
    return 'cost';
  }

  socIcon(soc: number, reserve: number = 20): string {
    if (soc >= 70) return 'battery-full-outline';
    if (soc >= reserve) return 'battery-half-outline';
    return 'battery-dead-outline';
  }

  seasonLabel(season: string): string {
    if (season === 'winter') return 'zima';
    if (season === 'autumn') return 'jesień';
    if (season === 'spring') return 'wiosna';
    if (season === 'summer') return 'lato';
    return season;
  }

  minutesAgo(date: Date | null): string {
    if (!date) return 'nigdy';
    const diffMs = Date.now() - date.getTime();
    const minutes = Math.max(0, Math.round(diffMs / 60000));
    if (minutes < 1) return 'przed chwilą';
    if (minutes === 1) return '1 minutę temu';
    return `${minutes} min temu`;
  }

  isNotToday(dayIso: string | null): boolean {
    if (!dayIso) return false;
    return dayIso !== todayIsoLocal();
  }

  formatDay(dayIso: string | null): string {
    if (!dayIso) return '';
    const [, month, day] = dayIso.split('-');
    return `${day}.${month}`;
  }
}
