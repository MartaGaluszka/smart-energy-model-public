import { Component, OnInit } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { ViewWillEnter } from '@ionic/angular';
import { filter } from 'rxjs/operators';
import { BatteryStateService } from './services/battery-state.service';

export type BatteryTab = 'settings' | 'schedule' | 'analytics';

@Component({
  selector: 'app-battery',
  templateUrl: './battery.page.html',
  styleUrls: ['./battery.page.scss'],
  standalone: false,
})
export class BatteryPage implements OnInit, ViewWillEnter {
  readonly tabs: ReadonlyArray<{ value: BatteryTab; label: string }> = [
    { value: 'settings', label: 'Ustawienia' },
    { value: 'schedule', label: 'Harmonogram' },
    { value: 'analytics', label: 'Analityka' },
  ];

  activeTab: BatteryTab = 'settings';

  constructor(
    private readonly router: Router,
    readonly stateService: BatteryStateService
  ) {}

  ngOnInit(): void {
    this.syncTabFromUrl();

    this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => this.syncTabFromUrl());
  }

  ionViewWillEnter(): void {
    // Zawsze odśwież z API przy wejściu na ekran (bez mocków / stale cache).
    this.stateService.loadSettings(true);
  }

  selectTab(tab: BatteryTab): void {
    if (this.activeTab === tab) {
      return;
    }
    this.activeTab = tab;
    this.router.navigate(['/tabs/battery', tab]);
  }

  onSave(): void {
    this.stateService.saveSettings().subscribe();
  }

  private syncTabFromUrl(): void {
    const url = this.router.url;
    if (url.includes('/schedule')) {
      this.activeTab = 'schedule';
    } else if (url.includes('/analytics')) {
      this.activeTab = 'analytics';
    } else {
      this.activeTab = 'settings';
    }
  }
}
