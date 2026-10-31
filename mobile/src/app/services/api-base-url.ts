import { Capacitor } from '@capacitor/core';
import { environment } from '../../environments/environment';
import { SIMULATOR_API_ORIGIN } from '../../environments/simulator-api-host';

const PLACEHOLDER_API_HOST = 'api.smartenergy.example.com';

function isLoopbackHost(host: string | undefined): boolean {
  return !host || host === 'localhost' || host === '127.0.0.1';
}

/**
 * Adres API w dev. W iOS Simulatorze 127.0.0.1 to pętla telefonu, nie Maca —
 * build:sim ustawia SIMULATOR_API_ORIGIN (IP LAN). Live-reload: ten sam host co
 * window.location (ng serve na LAN). Produkcja: environment.apiBaseUrl.
 *
 * Placeholder z environment.prod.ts NIGDY nie idzie do Simulatora — to był
 * błąd po `npm run build` (domyślnie production) zamiast `npm run build:sim`.
 */
export function resolveApiBaseUrl(): string {
  const configured = environment.apiBaseUrl;

  if (isPlaceholderApiUrl(configured)) {
    return resolveLocalDevApiUrl();
  }

  if (environment.production) {
    return configured;
  }

  const host = globalThis.location?.hostname;

  // iOS Simulator + loopback w WebView → zawsze IP Maca z build:sim (nie 127.0.0.1 telefonu).
  if (
    Capacitor.isNativePlatform() &&
    Capacitor.getPlatform() === 'ios' &&
    SIMULATOR_API_ORIGIN &&
    isLoopbackHost(host)
  ) {
    return SIMULATOR_API_ORIGIN;
  }

  if (host && !isLoopbackHost(host)) {
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

function isPlaceholderApiUrl(url: string): boolean {
  try {
    return new URL(url).hostname === PLACEHOLDER_API_HOST;
  } catch {
    return url.includes(PLACEHOLDER_API_HOST);
  }
}

function resolveLocalDevApiUrl(): string {
  if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios' && SIMULATOR_API_ORIGIN) {
    return SIMULATOR_API_ORIGIN;
  }
  const host = globalThis.location?.hostname;
  if (host && !isLoopbackHost(host)) {
    return `http://${host}:8000`;
  }
  return 'http://127.0.0.1:8000';
}
