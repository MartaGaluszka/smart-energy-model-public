import { Component } from '@angular/core';
import { BatteryStateService } from '../services/battery-state.service';

type SeasonMode = 'auto' | 'summer' | 'autumn' | 'spring' | 'winter';

@Component({
  selector: 'app-battery-settings',
  templateUrl: './battery-settings.page.html',
  styleUrls: ['../battery-shared.scss'],
  standalone: false,
})
export class BatterySettingsPage {
  /** Ostatnia kalibracja round-trip z liczników FoxESS (25–26.08.2026). */
  readonly efficiencyCalibrationLabel = '08.2026';
  readonly efficiencyNextReviewLabel = '08.2027';

  readonly seasonOptions: { value: SeasonMode; label: string }[] = [
    { value: 'auto', label: 'Auto' },
    { value: 'summer', label: 'Lato' },
    { value: 'autumn', label: 'Jesień' },
    { value: 'winter', label: 'Zima' },
    { value: 'spring', label: 'Wiosna' },
  ];

  private readonly recommendedReserve: Record<Exclude<SeasonMode, 'auto'>, number> = {
    summer: 20,
    autumn: 22,
    winter: 40,
    spring: 25,
  };

  constructor(readonly stateService: BatteryStateService) {}

  seasonLabel(season: string): string {
    const map: Record<string, string> = {
      summer: 'lato',
      autumn: 'jesień',
      spring: 'wiosna',
      winter: 'zima',
      auto: 'auto',
    };
    return map[season] ?? season;
  }

  onSeasonChange(value: string | number | undefined): void {
    if (typeof value !== 'string') return;
    if (!['auto', 'summer', 'autumn', 'spring', 'winter'].includes(value)) return;
    
    const season = value as SeasonMode;
    this.stateService.updateSettings({ season });
    this.applyRecommendedForSeason(season);
  }

  onSocMinChange(value: number): void {
    this.stateService.updateSettings({
      soc_min_percent: value,
      soc_reserve_percent: value, // Sync reserve
    });
  }

  onSocTargetChange(value: number): void {
    this.stateService.updateSettings({ soc_target_percent: value });
  }

  private resolvedSeasonKey(season: string): Exclude<SeasonMode, 'auto'> {
    if (season === 'auto') {
      const current = this.stateService.state();
      return (current?.season_resolved || 'summer') as Exclude<SeasonMode, 'auto'>;
    }
    return season as Exclude<SeasonMode, 'auto'>;
  }

  private applyRecommendedForSeason(season: SeasonMode): void {
    const key = this.resolvedSeasonKey(season);
    const rec = this.recommendedReserve[key] ?? 20;
    this.stateService.updateSettings({
      soc_min_percent: rec,
      soc_reserve_percent: rec,
    });
  }
}
