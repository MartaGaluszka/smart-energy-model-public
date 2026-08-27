import { Component, OnDestroy, OnInit } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { Observable, Subscription } from 'rxjs';
import { BatterySuggestionResponse } from '../services/api.service';
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
  private batterySub?: Subscription;

  constructor(private readonly homeData: HomeDataService) {}

  ngOnInit() {
    this.kpi$ = this.homeData.getKpi();
    this.sync$ = this.homeData.getSyncStatus();
    this.suggestions$ = this.homeData.getSuggestions();
    this.battery$ = this.homeData.getBatterySuggestion();
    this.batterySub = this.battery$.subscribe((row) => {
      this.socReserve = row?.soc_reserve_percent ?? 20;
    });
  }

  ngOnDestroy() {
    this.batterySub?.unsubscribe();
  }

  ionViewWillEnter() {
    this.homeData.refreshBatterySuggestion();
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
