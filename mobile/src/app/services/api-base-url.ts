import { environment } from '../../environments/environment';

/**
 * Adres API w dev. W iOS Simulatorze 127.0.0.1 to pętla telefonu, nie Maca —
 * gdy live-reload serwuje UI z LAN (np. http://192.168.x.x:8100), API musi iść
 * na ten sam host:8000. Produkcja zostaje przy stałym environment.apiBaseUrl.
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
  return configured;
}
