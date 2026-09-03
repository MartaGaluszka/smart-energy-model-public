import { Component, OnInit } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { ViewWillEnter } from '@ionic/angular';
import { filter } from 'rxjs/operators';
import { BatteryStateService } from './services/battery-state.service';

@Component({
  selector: 'app-battery',
  templateUrl: './battery.page.html',
  styleUrls: ['./battery.page.scss'],
  standalone: false,
})
export class BatteryPage implements OnInit, ViewWillEnter {
  activeTab = 'settings';

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

  onTabChange(): void {
    this.router.navigate(['/tabs/battery', this.activeTab]);
  }

  onSave(): void {
    this.stateService.saveSettings().subscribe();
  }

  private syncTabFromUrl(): void {
    const url = this.router.url;
    if (url.includes('/settings')) {
      this.activeTab = 'settings';
    } else if (url.includes('/schedule')) {
      this.activeTab = 'schedule';
    } else if (url.includes('/analytics')) {
      this.activeTab = 'analytics';
    }
  }
}
