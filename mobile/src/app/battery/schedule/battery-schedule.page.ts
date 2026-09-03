import { Component } from '@angular/core';
import { BatteryScheduleMode } from '../../services/api.service';
import { BatteryStateService } from '../services/battery-state.service';

@Component({
  selector: 'app-battery-schedule',
  templateUrl: './battery-schedule.page.html',
  styleUrls: ['../battery-shared.scss'],
  standalone: false,
})
export class BatterySchedulePage {
  readonly scheduleModes: { value: BatteryScheduleMode; label: string }[] = [
    { value: 'ForceCharge', label: 'Doładuj z sieci' },
    { value: 'SelfUse', label: 'Zasilaj dom' },
    { value: 'ForceDischarge', label: 'Oddaj do sieci' },
  ];

  readonly tariffPresets: { value: 'g11' | 'g12w' | 'g13'; label: string; hint: string }[] = [
    { value: 'g11', label: 'G11', hint: '1 blok (płaska)' },
    { value: 'g12w', label: 'G12w', hint: 'kilka okien' },
    { value: 'g13', label: 'G13', hint: 'więcej okien' },
  ];

  constructor(readonly stateService: BatteryStateService) {}

  estimatedDeltaSoc(): number {
    const state = this.stateService.state();
    const fcMax = state?.fc_max_minutes ?? 15;
    return Math.round((fcMax / 30) * 50);
  }

  fcWindowEndLabel(): string {
    const state = this.stateService.state();
    const startHour = state?.fc_night_start_hour ?? 22;
    const fcMax = state?.fc_max_minutes ?? 15;
    
    const startMin = Math.max(0, Math.min(23, Math.round(startHour))) * 60;
    const endTotal = (startMin + Math.max(0, Math.round(fcMax))) % (24 * 60);
    const h = Math.floor(endTotal / 60);
    const m = endTotal % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  fcWindowLabel(): string {
    const state = this.stateService.state();
    const startHour = state?.fc_night_start_hour ?? 22;
    const start = `${Math.round(startHour).toString().padStart(2, '0')}:00`;
    return `${start}–${this.fcWindowEndLabel()}`;
  }

  modeLabel(mode: string): string {
    return this.scheduleModes.find((m) => m.value === mode)?.label ?? mode;
  }

  canAddWindow(): boolean {
    const state = this.stateService.state();
    const maxWindows = state?.schedule_max_windows ?? 8;
    const currentCount = state?.schedule_windows?.length ?? 0;
    return currentCount < maxWindows;
  }

  addWindow(): void {
    if (!this.canAddWindow()) return;
    const state = this.stateService.state();
    const windows = state?.schedule_windows ?? [];
    this.stateService.updateSettings({
      schedule_windows: [
        ...windows,
        { start: '13:00', end: '14:00', mode: 'ForceCharge', enabled: false },
      ],
      schedule_preset: 'custom',
    });
  }

  removeWindow(index: number): void {
    const state = this.stateService.state();
    const windows = state?.schedule_windows ?? [];
    this.stateService.updateSettings({
      schedule_windows: windows.filter((_, i) => i !== index),
      schedule_preset: 'custom',
    });
  }

  applyTariffPreset(preset: string | number | undefined): void {
    if (typeof preset !== 'string') return;
    if (preset !== 'g11' && preset !== 'g12w' && preset !== 'g13') return;
    
    const state = this.stateService.state();
    const startHour = state?.fc_night_start_hour ?? 22;
    const maxWindows = state?.schedule_max_windows ?? 8;
    
    const nightStart = `${Math.round(startHour).toString().padStart(2, '0')}:00`;
    const nightEnd = this.fcWindowEndLabel();
    
    let windows: any[] = [];
    
    if (preset === 'g11') {
      windows = [{ start: nightStart, end: nightEnd, mode: 'ForceCharge', enabled: false }];
    } else if (preset === 'g13') {
      windows = [
        { start: '06:00', end: '09:00', mode: 'SelfUse' as const, enabled: false },
        { start: '09:00', end: '13:00', mode: 'SelfUse' as const, enabled: false },
        { start: '13:00', end: '15:00', mode: 'ForceCharge' as const, enabled: false },
        { start: '15:00', end: '17:00', mode: 'SelfUse' as const, enabled: false },
        { start: '17:00', end: '22:00', mode: 'SelfUse' as const, enabled: false },
        { start: '22:00', end: '01:00', mode: 'ForceCharge' as const, enabled: false },
        { start: '04:00', end: '06:00', mode: 'ForceCharge' as const, enabled: false },
      ].slice(0, maxWindows);
    } else {
      // G12w
      windows = [
        { start: '06:00', end: '13:00', mode: 'SelfUse' as const, enabled: false },
        { start: '13:00', end: '15:00', mode: 'ForceCharge' as const, enabled: false },
        { start: '15:00', end: '22:00', mode: 'SelfUse' as const, enabled: false },
        { start: '22:00', end: '01:00', mode: 'ForceCharge' as const, enabled: false },
        { start: '04:00', end: '06:00', mode: 'ForceCharge' as const, enabled: false },
      ].slice(0, maxWindows);
    }
    
    this.stateService.updateSettings({
      schedule_windows: windows,
      schedule_preset: preset,
    });
  }

  syncNightIntoSchedule(): void {
    const state = this.stateService.state();
    const windows = state?.schedule_windows ?? [];
    const nightStart = `${Math.round(state?.fc_night_start_hour ?? 22).toString().padStart(2, '0')}:00`;
    const nightEnd = this.fcWindowEndLabel();
    
    let idx = windows.findIndex((w) => w.mode === 'ForceCharge' && w.start === '22:00');
    if (idx < 0) {
      idx = windows.findIndex((w) => w.mode === 'ForceCharge');
    }
    
    if (idx >= 0) {
      const copy = [...windows];
      copy[idx] = { ...copy[idx], start: nightStart, end: nightEnd, enabled: false };
      this.stateService.updateSettings({
        schedule_windows: copy,
        schedule_preset: 'custom',
      });
      return;
    }
    
    if (this.canAddWindow()) {
      this.stateService.updateSettings({
        schedule_windows: [
          ...windows,
          { start: nightStart, end: nightEnd, mode: 'ForceCharge', enabled: false },
        ],
        schedule_preset: 'custom',
      });
    }
  }

  onWindowToggle(index: number, enabled: boolean): void {
    const state = this.stateService.state();
    const windows = state?.schedule_windows ?? [];
    const copy = [...windows];
    copy[index] = { ...copy[index], enabled };
    this.stateService.updateSettings({
      schedule_windows: copy,
      schedule_preset: 'custom',
    });
  }

  onWindowTimeChange(index: number, field: 'start' | 'end', value: string): void {
    const state = this.stateService.state();
    const windows = state?.schedule_windows ?? [];
    const copy = [...windows];
    copy[index] = { ...copy[index], [field]: value };
    this.stateService.updateSettings({
      schedule_windows: copy,
      schedule_preset: 'custom',
    });
  }

  onWindowModeChange(index: number, mode: BatteryScheduleMode): void {
    const state = this.stateService.state();
    const windows = state?.schedule_windows ?? [];
    const copy = [...windows];
    copy[index] = { ...copy[index], mode };
    this.stateService.updateSettings({
      schedule_windows: copy,
      schedule_preset: 'custom',
    });
  }

  onFcStartChange(value: number): void {
    this.stateService.updateSettings({ fc_night_start_hour: value });
  }

  onFcMaxChange(value: number): void {
    this.stateService.updateSettings({ fc_max_minutes: value });
  }
}
