import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';
import { HomeDataService, HomeKpi, SyncStatus, Suggestion } from '../services/home-data.service';
import { todayIsoLocal } from '../utils/date-utils';

@Component({
  selector: 'app-tab1',
  templateUrl: 'tab1.page.html',
  styleUrls: ['tab1.page.scss'],
  standalone: false,
})
export class Tab1Page implements OnInit {
  kpi$!: Observable<HomeKpi>;
  sync$!: Observable<SyncStatus>;
  suggestions$!: Observable<Suggestion[]>;

  constructor(private readonly homeData: HomeDataService) {}

  ngOnInit() {
    this.kpi$ = this.homeData.getKpi();
    this.sync$ = this.homeData.getSyncStatus();
    this.suggestions$ = this.homeData.getSuggestions();
  }

  onSync() {
    this.homeData.triggerSync().subscribe();
  }

  socColor(soc: number): string {
    if (soc >= 50) return 'moss';
    if (soc >= 20) return 'warning';
    return 'cost';
  }

  socIcon(soc: number): string {
    if (soc >= 70) return 'battery-full-outline';
    if (soc >= 20) return 'battery-half-outline';
    return 'battery-dead-outline';
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
