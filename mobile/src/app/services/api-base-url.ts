import { Capacitor } from '@capacitor/core';
import { environment } from '../../environments/environment';
import { SIMULATOR_API_ORIGIN } from '../../environments/simulator-api-host';

/**
 * Adres API w dev. W iOS Simulatorze 127.0.0.1 to pętla telefonu, nie Maca —
 * build:sim ustawia SIMULATOR_API_ORIGIN (IP LAN). Live-reload: ten sam host co
 * window.location (ng serve na LAN). Produkcja: environment.apiBaseUrl.
 */
export function resolveApiBaseUrl(): string {
  const configured = environment.apiBaseUrl;
  if (environment.production) {
    return configured;
  }

  const host = globalThis.location?.hostname;
  if (host && host !== 'localhost' && host !== '127.0.0.1') {
    try {
      const url = new URL(configured);
      url.hostname = host;
      return url.origin;
    } catch {
      return `http://${host}:8000`;
    }
  }

  if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios' && SIMULATOR_API_ORIGIN) {
    return SIMULATOR_API_ORIGIN;
  }

  return configured;
}
