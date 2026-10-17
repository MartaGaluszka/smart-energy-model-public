import { Injectable } from '@angular/core';

/** Skok z Rytmu domu do godzin na Prognozie. Zużywany przy wejściu na zakładkę. */
@Injectable({ providedIn: 'root' })
export class ForecastBridgeService {
  private pendingDay: string | null = null;

  open(dayIso: string): void {
    this.pendingDay = dayIso.slice(0, 10);
  }

  hasPending(): boolean {
    return this.pendingDay != null;
  }

  consume(): string | null {
    const day = this.pendingDay;
    this.pendingDay = null;
    return day;
  }
}
