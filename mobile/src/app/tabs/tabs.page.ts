import { Component } from '@angular/core';
import { ForecastDataService } from '../services/forecast-data.service';

@Component({
  selector: 'app-tabs',
  templateUrl: 'tabs.page.html',
  styleUrls: ['tabs.page.scss'],
  standalone: false,
})
export class TabsPage {
  constructor(private readonly forecastData: ForecastDataService) {}

  /** Uzupełnia ionViewDidEnter na Tab3 — pewny reset na Dziś przy kliknięciu Prognoza. */
  onTabsChange(event: { tab: string }): void {
    if (event?.tab === 'tab3') {
      this.forecastData.focusPrognozaTab();
    }
  }
}
