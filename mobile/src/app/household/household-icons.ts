/**
 * Własne ikony AGD/posiłków — ten sam format co ionicons (`data:image/svg+xml;utf8,...`).
 * Ionicons nie ma pralki, suszarki, bochenka, grzejnika, talerza.
 */
function ionDataUrl(innerSvg: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" class="ionicon" viewBox="0 0 512 512">${innerSvg}</svg>`;
  // encodeURIComponent — pewniej w WKWebView niż surowy utf8 jak w bundlu ionicons
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export const HOUSEHOLD_CUSTOM_ICONS: Record<string, string> = {
  /** Filiżanka — śniadanie (ionicons cafe bywa pusty w modalu WKWebView). */
  'se-breakfast': ionDataUrl(
    `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" stroke-linejoin="round" d="M112 200h240v120c0 44-36 80-80 80h-80c-44 0-80-36-80-80V200z"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" d="M352 240h40c36 0 64 28 64 64s-28 64-64 64h-40"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M160 128c8-24 24-40 40-48M224 112c8-20 20-32 36-40"/>`,
  ),
  'se-plate': ionDataUrl(
    `<circle cx="256" cy="270" r="170" fill="none" stroke="currentColor" stroke-width="36"/>` +
      `<circle cx="256" cy="270" r="88" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M168 210c28-32 64-44 88-44s60 12 88 44"/>`,
  ),
  /** Widelec + nóż — obiad / indukcja. */
  'se-utensils': ionDataUrl(
    `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" d="M144 96v140c0 28 20 48 48 48h0"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M128 96v88M160 96v88M192 96v88"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" d="M192 284v132"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" stroke-linejoin="round" d="M320 96c40 40 48 96 48 128v48c0 20-16 36-36 36h-24V96z"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" d="M308 308v108"/>`,
  ),
  /** Zmywarka — szafka AGD z półką na naczynia. */
  'se-dishwasher': ionDataUrl(
    `<rect x="96" y="64" width="320" height="384" rx="36" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M96 176h320"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" d="M160 240h192M176 288h160M192 336h128"/>` +
      `<circle cx="176" cy="120" r="14" fill="currentColor"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" d="M224 120h160"/>`,
  ),
  /** Piekarnik — szafka z szybą i uchwytem, osobno od maszynki do chleba. */
  'se-oven': ionDataUrl(
    `<rect x="88" y="72" width="336" height="368" rx="32" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M88 168h336"/>` +
      `<circle cx="168" cy="120" r="14" fill="currentColor"/>` +
      `<circle cx="232" cy="120" r="14" fill="currentColor"/>` +
      `<rect x="156" y="214" width="200" height="140" rx="18" fill="none" stroke="currentColor" stroke-width="24"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M200 400h112"/>`,
  ),
  /** Mac mini — płaska skrzynka. */
  'se-mac-mini': ionDataUrl(
    `<rect x="96" y="176" width="320" height="160" rx="28" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<circle cx="256" cy="256" r="16" fill="currentColor"/>`,
  ),
  /** MacBook — ekran i klawiatura, bez znaku firmy. */
  'se-macbook': ionDataUrl(
    `<rect x="128" y="72" width="256" height="176" rx="16" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linejoin="round" d="M72 280h368l-36 72H108z"/>`,
  ),
  /** Dreamy — odkurzacz, dysk z góry. */
  'se-robot': ionDataUrl(
    `<circle cx="256" cy="268" r="156" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<circle cx="256" cy="248" r="40" fill="none" stroke="currentColor" stroke-width="24"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M168 360c24 28 56 44 88 44s64-16 88-44"/>` +
      `<circle cx="256" cy="248" r="10" fill="currentColor"/>`,
  ),
  'se-bread': ionDataUrl(
    `<path fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round" stroke-linejoin="round" d="M96 220c0-56 48-100 112-112 28-40 88-56 136-28 56-8 112 32 120 88 40 16 64 56 56 100v48c0 44-36 80-80 80H152c-44 0-80-36-80-80v-40c0-20 4-40 24-56z"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" d="M168 248c24-20 48-28 72-28s48 8 72 28M248 300v72"/>`,
  ),
  'se-radiator': ionDataUrl(
    `<rect x="80" y="128" width="352" height="256" rx="24" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M144 168v176M208 168v176M272 168v176M336 168v176M400 168v176"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M112 420h48M352 420h48"/>`,
  ),
  /** Podłoga + wężownica + fale ciepła — zima / ogrzewanie podłogowe. */
  'se-floor-heat': ionDataUrl(
    `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M96 200c20-28 44-40 64-40s44 12 64 40M288 200c20-28 44-40 64-40s44 12 64 40"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="28" stroke-linecap="round" d="M128 148c16-20 32-28 48-28s32 8 48 28M288 148c16-20 32-28 48-28s32 8 48 28"/>` +
      `<rect x="64" y="280" width="384" height="140" rx="20" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" d="M112 320h288c0 28-24 44-48 44H160c-24 0-48 16-48 44h288"/>`,
  ),
  'se-washer': ionDataUrl(
    `<rect x="96" y="64" width="320" height="384" rx="36" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<circle cx="256" cy="280" r="96" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<circle cx="256" cy="280" r="40" fill="none" stroke="currentColor" stroke-width="24"/>` +
      `<circle cx="176" cy="128" r="14" fill="currentColor"/>` +
      `<circle cx="224" cy="128" r="14" fill="currentColor"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" d="M304 120h64"/>`,
  ),
  'se-dryer': ionDataUrl(
    `<rect x="96" y="64" width="320" height="384" rx="36" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<circle cx="256" cy="280" r="96" fill="none" stroke="currentColor" stroke-width="32"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" d="M216 248c16-28 40-40 64-28s40 40 24 68"/>` +
      `<circle cx="176" cy="128" r="14" fill="currentColor"/>` +
      `<circle cx="224" cy="128" r="14" fill="currentColor"/>` +
      `<path fill="none" stroke="currentColor" stroke-width="24" stroke-linecap="round" d="M304 120h64"/>`,
  ),
};

export function isHouseholdCustomIcon(name: string): boolean {
  return Object.prototype.hasOwnProperty.call(HOUSEHOLD_CUSTOM_ICONS, name);
}
