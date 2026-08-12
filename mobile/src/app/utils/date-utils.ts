/**
 * Formatuje datę do "YYYY-MM-DD" używając SKŁADOWYCH LOKALNYCH (getFullYear/getMonth/getDate),
 * a nie `Date.prototype.toISOString()`. `toISOString()` zawsze konwertuje instant do UTC — w
 * strefie z dodatnim przesunięciem (Europe/Warsaw, UTC+1/+2) lokalna północ danego dnia to wciąż
 * POPRZEDNI dzień w UTC, więc `toISOString().slice(0, 10)` regularnie cofa datę o jeden dzień
 * (a przy krokowej nawigacji dzień po dniu — psuje całą logikę, bo każdy krok "ucieka" o 1 dzień
 * dodatkowo w tę samą stronę).
 */
export function toLocalIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function todayIsoLocal(): string {
  return toLocalIsoDate(new Date());
}

/** Przesuwa datę (ISO "YYYY-MM-DD") o `deltaDays` dni, w lokalnej strefie czasowej. */
export function shiftIsoDate(dayIso: string, deltaDays: number): string {
  const d = new Date(`${dayIso}T00:00:00`);
  d.setDate(d.getDate() + deltaDays);
  return toLocalIsoDate(d);
}
