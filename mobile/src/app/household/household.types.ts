/** Katalog typów kalendarza — zgodny z PROJEKT §10.1. */
export type HouseholdImpact = 'up' | 'down' | 'neutral';

export interface HouseholdEventTypeDef {
  value: string;
  label: string;
  /** Krótka etykieta w gęstej siatce modału (opcjonalnie). */
  shortLabel?: string;
  icon: string;
  /**
   * Trzy stopnie obciążenia: zieleń = mało, złoto = średnio, czerwień = najwięcej.
   */
  tint: 'moss' | 'solar' | 'grid' | 'muted' | 'cost';
  defaultImpact: HouseholdImpact;
  /** Szacunek kWh do insightu (MVP). */
  estimatedKwh: number;
  /** Szacunek zł = kWh × G12w spread (~0,36). */
  insightHint: string;
}

/** Szybkie scenariusze w sheetcie — mogą zaznaczyć kilka typów naraz. */
export interface HouseholdScenario {
  id: string;
  label: string;
  blurb: string;
  icon: string;
  /** Typy do zaznaczenia (multi). */
  eventTypes: ReadonlyArray<string>;
}

export const HOUSEHOLD_SCENARIOS: ReadonlyArray<HouseholdScenario> = [
  {
    id: 'laundry',
    label: 'Dzień prania',
    blurb: 'Pranie + suszarka — możesz dodać zmywarkę',
    icon: 'se-washer',
    eventTypes: ['pranie', 'suszarka'],
  },
  {
    id: 'heat',
    label: 'Upał / AC',
    blurb: 'Klimatyzacja — karta na Home',
    icon: 'thermometer-outline',
    eventTypes: ['klimatyzacja'],
  },
  {
    id: 'away',
    label: 'Wyjazd',
    blurb: 'Pusty dom — łagodniejszy bufor',
    icon: 'airplane-outline',
    eventTypes: ['wyjazd'],
  },
  {
    id: 'floor',
    label: 'Podłogówka',
    blurb: 'Zima — doradca szacuje kWh nocy z T',
    icon: 'se-floor-heat',
    eventTypes: ['podlogowka'],
  },
];

/**
 * Kolejność UI: posiłki → zmywarka → chleb → grzejnik → pranie → suszarka → reszta.
 * Ikony `se-*` = własne SVG (household-icons.ts).
 */
export const HOUSEHOLD_EVENT_TYPES: ReadonlyArray<HouseholdEventTypeDef> = [
  {
    value: 'sniadanie',
    label: 'Śniadanie',
    icon: 'se-breakfast',
    tint: 'solar',
    defaultImpact: 'up',
    estimatedKwh: 1.4,
    insightHint: 'Budżet ~1,3 kWh przed PV — wpływa na bufor rano.',
  },
  {
    value: 'obiad',
    label: 'Obiad / indukcja',
    shortLabel: 'Obiad',
    icon: 'se-utensils',
    tint: 'solar',
    defaultImpact: 'up',
    estimatedKwh: 2.2,
    insightHint: 'Więcej niż śniadanie i kolacja, ok. 2,2 kWh — najlepiej w szczycie produkcji.',
  },
  {
    value: 'kolacja',
    label: 'Kolacja',
    icon: 'se-plate',
    tint: 'solar',
    defaultImpact: 'up',
    estimatedKwh: 1.4,
    insightHint:
      'Jak śniadanie ~1,3–1,4 kWh (ciepłe + czajnik / piekarnik) — wieczór bez PV, pilnuj SoC przed 22.',
  },
  {
    value: 'zmywarka',
    label: 'Zmywarka',
    icon: 'se-dishwasher',
    tint: 'moss',
    defaultImpact: 'up',
    estimatedKwh: 1.2,
    insightHint: 'Szczyt PV albo tania 13–15 / po 22.',
  },
  {
    value: 'chleb',
    label: 'Pieczenie chleba',
    shortLabel: 'Chleb',
    icon: 'se-bread',
    tint: 'moss',
    defaultImpact: 'up',
    estimatedKwh: 0.8,
    insightHint: 'Lekkie obciążenie — można równolegle z innym AGD.',
  },
  {
    value: 'piekarnik',
    label: 'Piekarnik',
    icon: 'se-oven',
    tint: 'solar',
    defaultImpact: 'up',
    estimatedKwh: 2,
    insightHint: 'Około 2 kWh, więcej niż maszynka do chleba. Najlepiej, gdy dach produkuje.',
  },
  {
    value: 'grzejnik_lazienka',
    label: 'Grzejnik łazienka',
    shortLabel: 'Grzejnik',
    icon: 'se-radiator',
    tint: 'moss',
    defaultImpact: 'up',
    estimatedKwh: 0.75,
    insightHint: 'Dodaje ~0,75 kWh do budżetu nocy przed FC.',
  },
  {
    value: 'podlogowka',
    label: 'Podłogówka (zima)',
    shortLabel: 'Podłoga',
    icon: 'se-floor-heat',
    tint: 'cost',
    defaultImpact: 'up',
    estimatedKwh: 1.2,
    insightHint:
      'Doradca liczy kWh nocy z T (cykle bufora ~0,58 kWh) i cel SoC@22 — nie stałe 30%.',
  },
  {
    value: 'pranie',
    label: 'Pranie',
    icon: 'se-washer',
    tint: 'solar',
    defaultImpact: 'up',
    estimatedKwh: 1.5,
    insightHint: 'Najlepiej w szczycie PV; przy słońcu pomiń nocne FC.',
  },
  {
    value: 'suszarka',
    label: 'Suszarka',
    icon: 'se-dryer',
    tint: 'solar',
    defaultImpact: 'up',
    estimatedKwh: 1.2,
    insightHint: 'Po praniu; cykl ~1–1,5 kWh przy SoC wysokim — wieczorem z baterii.',
  },
  {
    value: 'odkurzacz',
    label: 'Dreamy',
    icon: 'se-robot',
    tint: 'moss',
    defaultImpact: 'up',
    estimatedKwh: 0.2,
    insightHint: 'Około 0,2 kWh na jedno przejście. Mało wobec reszty AGD.',
  },
  {
    value: 'mac_mini',
    label: 'Mac mini',
    icon: 'se-mac-mini',
    tint: 'moss',
    defaultImpact: 'up',
    estimatedKwh: 0.2,
    insightHint: 'Zwykły dzień pracy, około 0,2 kWh. Mało wobec AGD.',
  },
  {
    value: 'macbook',
    label: 'MacBook Pro',
    shortLabel: 'MacBook',
    icon: 'se-macbook',
    tint: 'moss',
    defaultImpact: 'up',
    estimatedKwh: 1.12,
    insightHint: '8 godzin pracy przy 140 W to około 1,1 kWh.',
  },
  {
    value: 'przetwory',
    label: 'Przetwory',
    icon: 'basket-outline',
    tint: 'cost',
    defaultImpact: 'up',
    estimatedKwh: 10,
    insightHint: 'Duży load dzienne — następny dzień: pilnuj SoC @22.',
  },
  {
    value: 'klimatyzacja',
    label: 'Klimatyzacja / upał',
    shortLabel: 'AC / upał',
    icon: 'thermometer-outline',
    tint: 'cost',
    defaultImpact: 'up',
    estimatedKwh: 3,
    insightHint: 'Wyższa rezerwa SoC wieczorem — karta AC na Home.',
  },
  {
    value: 'wyjazd',
    label: 'Wyjazd',
    icon: 'airplane-outline',
    tint: 'moss',
    defaultImpact: 'down',
    estimatedKwh: 0,
    insightHint: 'Niższe zużycie — łagodniejszy bufor / standby.',
  },
  {
    value: 'ferie',
    label: 'Ferie / wakacje',
    shortLabel: 'Ferie',
    icon: 'sunny-outline',
    tint: 'moss',
    defaultImpact: 'down',
    estimatedKwh: 0,
    insightHint: 'Tryb urlopowy — mniej obciążenia domu.',
  },
];

/** Spread G12w tania↔droga — szacunek insightu (zł/kWh). */
export const HOUSEHOLD_G12W_SPREAD_PLN = 0.36;

/** Wszystkie typy — kolejne kliknięcie w sheetcie dodaje kolejny wpis (×n). */
export function isStackableEventType(_type: string): boolean {
  return true;
}

export function eventTypeDef(type: string): HouseholdEventTypeDef | undefined {
  const key = (type || '').trim().toLowerCase();
  const aliases: Record<string, string> = {
    upal: 'klimatyzacja',
    'upał': 'klimatyzacja',
    ac: 'klimatyzacja',
    wakacje: 'ferie',
    kolacja_indukcja: 'kolacja',
    ogrzewanie_podlogowe: 'podlogowka',
    podłoga: 'podlogowka',
    podlogowka_zima: 'podlogowka',
  };
  const resolved = aliases[key] ?? key;
  return HOUSEHOLD_EVENT_TYPES.find((t) => t.value === resolved);
}

export function estimateInsightPln(type: string): number | null {
  const def = eventTypeDef(type);
  if (!def || def.estimatedKwh <= 0) return null;
  return Math.round(def.estimatedKwh * HOUSEHOLD_G12W_SPREAD_PLN * 100) / 100;
}

/** Jedno zdanie doradcy dla wybranego dnia (metafora rytmu, nie kW). */
export function dayAdvisorLine(
  eventTypes: string[],
  extraTypes: ReadonlyArray<HouseholdEventTypeDef> = [],
): string {
  const keys = eventTypes.map((t) => eventTypeDef(t)?.value ?? t);
  if (keys.includes('pranie')) {
    return 'Pranie jest w planie. Przy dobrej produkcji z dachu wieczorne ładowanie z sieci nie będzie potrzebne.';
  }
  if (keys.includes('kolacja')) {
    return 'Kolacja zużywa tyle samo energii co śniadanie.';
  }
  if (keys.includes('klimatyzacja')) {
    return 'W planie jest klimatyzacja. Na stronie głównej pojawi się podpowiedź, kiedy ją wyłączyć.';
  }
  if (keys.includes('wyjazd') || keys.includes('ferie')) {
    return 'W planie jest wyjazd. Nie ma potrzeby trzymać baterii w pełni naładowanej.';
  }
  if (keys.includes('przetwory')) {
    return 'Przetwory zużywają dużo energii. Następnego dnia warto sprawdzić stan baterii przed 22.';
  }
  if (keys.includes('grzejnik_lazienka')) {
    return 'Grzejnik w łazience zwiększy zużycie energii w nocy.';
  }
  if (keys.includes('podlogowka')) {
    return 'Podłogówka pracuje w nocy. Przy niższej temperaturze warto zostawić więcej energii w baterii przed 22.';
  }
  if (keys.includes('sniadanie')) {
    return 'Śniadanie przypada rano, zanim instalacja zacznie produkować. Energia pójdzie z baterii.';
  }
  if (keys.includes('obiad')) {
    return 'Obiad zużywa więcej energii niż śniadanie i kolacja. Najkorzystniej ugotować go, gdy dach produkuje.';
  }
  if (keys.includes('piekarnik')) {
    return 'Piekarnik zużywa około 2 kWh. Najkorzystniej włączyć go, gdy dach produkuje.';
  }
  if (keys.includes('odkurzacz')) {
    return 'Dreamy zużywa niewiele, około 0,2 kWh na jedno przejście.';
  }
  if (keys.includes('mac_mini') && keys.includes('macbook')) {
    return 'Mac mini i MacBook Pro przez 8 godzin to razem około 1,3 kWh.';
  }
  if (keys.includes('macbook')) {
    return 'MacBook Pro przez 8 godzin przy ładowarce 140 W to około 1,1 kWh.';
  }
  if (keys.includes('mac_mini')) {
    return 'Mac mini zużywa około 0,2 kWh w zwykły dzień pracy.';
  }
  const custom = extraTypes.find((d) => keys.includes(d.value));
  if (custom) {
    return `${custom.label} jest w planie, około ${fmtKwh(custom.estimatedKwh)} kWh.`;
  }
  if (keys.length) {
    return 'Ten plan zostanie uwzględniony przy ustawieniu baterii.';
  }
  return 'Zaznacz plan dnia, a sprawdzimy, czy energii wystarczy.';
}

/** Domyślna pojemność, gdy ustawienia baterii nie mają wartości. */
export const HOUSEHOLD_DEFAULT_CAPACITY_KWH = 10.36;

export type DayBudgetVerdict = 'ok' | 'tight' | 'short' | 'empty';
/** Dziś = produkcja Fox; kolejne dni = prognoza modelu. */
export type PvBudgetSource = 'actual' | 'forecast' | null;

export interface DayEnergyBudget {
  planKwh: number;
  pvKwh: number | null;
  pvSource: PvBudgetSource;
  socPercent: number | null;
  batteryUsableKwh: number;
  coverKwh: number | null;
  verdict: DayBudgetVerdict;
  summaryLine: string;
  /** Czy bateria powyżej 10% pokryje nocne grzanie i tło domu do 8:00. */
  morningLine: string | null;
  /** Dziś: ile z planu już poszło z prądu (zrobione + trwa). Tylko gdy podano `progress`. */
  doneKwh?: number;
  /** Dziś: ile jeszcze zostało do zrobienia. */
  remainingKwh?: number;
  /** Dziś: „Już zrobione … Jeszcze przed Tobą …”. */
  progressLine?: string | null;
  hasProgress?: boolean;
}

/** Podział dzisiejszych ikon na te, które już pobrały prąd, i te, które jeszcze czekają. */
export interface DayProgressInput {
  /** Zrobione albo właśnie trwają. */
  done: string[];
  /** Jeszcze nie ruszyły (bez godziny albo z planowaną godziną). */
  todo: string[];
  /** Prognoza PV od teraz do wieczora, kWh. */
  remainingPvKwh?: number | null;
}

export function fmtKwh(n: number): string {
  const rounded = Math.round(n * 10) / 10;
  return (Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)).replace('.', ',');
}

/** Ikony do własnej pozycji — nazwy ionicons, bez własnych rysunków. */
export const HOUSEHOLD_CUSTOM_ICON_CHOICES: ReadonlyArray<{ name: string; label: string }> = [
  { name: 'car-outline', label: 'Auto' },
  { name: 'flash-outline', label: 'Prąd' },
  { name: 'construct-outline', label: 'Narzędzia' },
  { name: 'thermometer-outline', label: 'Ciepło' },
  { name: 'home-outline', label: 'Dom' },
  { name: 'water-outline', label: 'Woda' },
  { name: 'laptop-outline', label: 'Sprzęt' },
  { name: 'leaf-outline', label: 'Ogród' },
];

/** Zieleń do ~1,2 kWh, złoto do ~2,5, wyżej czerwień. */
export function tintForEstimatedKwh(kwh: number): 'moss' | 'solar' | 'cost' {
  if (kwh <= 1.2) return 'moss';
  if (kwh <= 2.5) return 'solar';
  return 'cost';
}

export function customEventValue(id: number): string {
  return `c${id}`;
}

export function customTypeDef(row: { id: number; label: string; icon: string; kwh: number }): HouseholdEventTypeDef {
  return {
    value: customEventValue(row.id),
    label: row.label,
    icon: row.icon,
    tint: tintForEstimatedKwh(row.kwh),
    defaultImpact: 'up',
    estimatedKwh: row.kwh,
    insightHint: `Około ${fmtKwh(row.kwh)} kWh na jedno włączenie.`,
  };
}

function defForEvent(type: string, extraTypes: ReadonlyArray<HouseholdEventTypeDef> = []): HouseholdEventTypeDef | undefined {
  return extraTypes.find((d) => d.value === type) ?? eventTypeDef(type);
}

/** Suma szacunków kWh z katalogu (wyjazd / ferie = 0). Własne pozycje dochodzą w extraTypes. */
export function sumPlannedEventKwh(
  eventTypes: string[],
  extraTypes: ReadonlyArray<HouseholdEventTypeDef> = [],
): number {
  let sum = 0;
  for (const t of eventTypes) {
    const def = defForEvent(t, extraTypes);
    if (def && def.estimatedKwh > 0 && def.defaultImpact !== 'down') {
      sum += def.estimatedKwh;
    }
  }
  return Math.round(sum * 100) / 100;
}

/** Zmierzone kWh bufora wchodzą raz, zamiast katalogu podłogi (także przy kilku wpisach). */
export function applyMeasuredFloorHeat(
  planKwh: number,
  eventTypes: string[],
  extraTypes: ReadonlyArray<HouseholdEventTypeDef>,
  floorHeatKwh: number | null | undefined,
): number {
  if (floorHeatKwh == null || !Number.isFinite(floorHeatKwh) || floorHeatKwh <= 0) {
    return planKwh;
  }
  let catalog = 0;
  for (const type of eventTypes) {
    const def = defForEvent(type, extraTypes);
    if (def?.value === 'podlogowka') {
      catalog += def.estimatedKwh;
    }
  }
  return Math.round((planKwh - catalog + floorHeatKwh) * 100) / 100;
}

export function usableBatteryKwh(
  socPercent: number | null | undefined,
  capacityKwh: number | null | undefined,
  reservePercent: number | null | undefined,
): number {
  const cap = capacityKwh != null && capacityKwh > 0 ? capacityKwh : HOUSEHOLD_DEFAULT_CAPACITY_KWH;
  const reserve = reservePercent != null ? reservePercent : 20;
  if (socPercent == null || !Number.isFinite(socPercent)) return 0;
  const usablePct = Math.max(0, socPercent - reserve);
  return Math.round(((usablePct / 100) * cap) * 100) / 100;
}

type PlanBudgetInput = {
  eventTypes: string[];
  pvKwh?: number | null;
  pvSource?: PvBudgetSource;
  socPercent?: number | null;
  capacityKwh?: number | null;
  reservePercent?: number | null;
  extraTypes?: ReadonlyArray<HouseholdEventTypeDef>;
  /** Zmierzone kWh bufora z Foxa. Zastępuje katalogowe 1,2 kWh ikony podłogi. */
  floorHeatKwh?: number | null;
  /** Cykle bufora od północy do 10:00 — wzorzec „takiej nocy” do rana. */
  nightHeatKwh?: number | null;
  now?: Date;
  /** Dziś: ile kWh dom już zużył według falownika (Fox). Zastępuje szacunek z ikon w „Już zużyte”. */
  loadKwh?: number | null;
  /** Dziś: co już zrobione, a co jeszcze przed Tobą. Bez tego budżet liczy cały plan jak dla przyszłych dni. */
  progress?: DayProgressInput;
};

/** Czy plan ikon mieści się w prognozie dnia i energii z baterii powyżej rezerwy. */
export function buildDayEnergyBudget(input: PlanBudgetInput): DayEnergyBudget {
  const base = buildPlanBudget(input);
  if (!input.progress || base.planKwh <= 0) return base;
  return applyDayProgress(base, input, input.progress);
}

const NO_ENERGY_TYPES = new Set(['wyjazd', 'ferie']);

/** Pracują cały dzień w tle: nie mają „startu”, więc nigdy nie są „do zrobienia”. */
export const BACKGROUND_EVENT_TYPES: ReadonlySet<string> = new Set(['mac_mini', 'macbook', 'podlogowka']);

export function isBackgroundType(type: string | null | undefined): boolean {
  if (!type) return false;
  return BACKGROUND_EVENT_TYPES.has(eventTypeDef(type)?.value ?? type);
}

function progressNames(types: string[], extra: ReadonlyArray<HouseholdEventTypeDef>): string {
  const counts = new Map<string, number>();
  for (const type of types) {
    const def = defForEvent(type, extra);
    if (def && NO_ENERGY_TYPES.has(def.value)) continue;
    const label = (def?.shortLabel ?? def?.label ?? type).toLowerCase();
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()].map(([label, n]) => (n > 1 ? `${label} ×${n}` : label)).join(', ');
}

/** „komputery i podłogówka” — Mac mini i MacBook razem, jako jedno słowo. */
function backgroundPhrase(types: string[], extra: ReadonlyArray<HouseholdEventTypeDef>): string {
  const values = types.map((type) => defForEvent(type, extra)?.value ?? type);
  const computers = values.filter((value) => value === 'mac_mini' || value === 'macbook').length;
  const phrases: string[] = [];
  if (computers) phrases.push(computers > 1 ? 'komputery' : 'komputer');
  if (values.includes('podlogowka')) phrases.push('podłogówka');
  return phrases.join(' i ');
}

/**
 * Dziś: „Już zużyte” to odczyt z falownika, reszta dnia to szacunek z ikon.
 * Budżet liczony od tego, co zostało; to, co już pobrało prąd, tylko opisujemy.
 */
function applyDayProgress(
  base: DayEnergyBudget,
  input: PlanBudgetInput,
  progress: DayProgressInput,
): DayEnergyBudget {
  const extra = input.extraTypes ?? [];
  const isBg = (type: string) => isBackgroundType(defForEvent(type, extra)?.value ?? type);
  // Mac mini, MacBook i podłogówka pracują w tle cały dzień — nigdy nie są „do zrobienia”.
  const todo = progress.todo.filter((type) => !isBg(type));
  const remainingKwh = sumPlannedEventKwh(todo, extra);
  const loadKwh =
    input.loadKwh != null && Number.isFinite(input.loadKwh) && input.loadKwh >= 0
      ? Math.round(input.loadKwh * 10) / 10
      : null;
  const doneKwh = loadKwh ?? Math.round(Math.max(0, base.planKwh - remainingKwh) * 100) / 100;

  // Harmonogram: zrobione, co zostaje, czy starczy prądu, co pracuje w tle.
  const doneNames = progressNames(progress.done.filter((type) => !isBg(type)), extra);
  const todoNames = progressNames(todo, extra);
  const bgPhrase = backgroundPhrase(progress.done.filter(isBg), extra);

  const restPv =
    progress.remainingPvKwh != null && Number.isFinite(progress.remainingPvKwh)
      ? Math.max(0, Math.round(progress.remainingPvKwh * 10) / 10)
      : null;
  const battery = base.batteryUsableKwh;
  const cover = Math.round(((restPv ?? 0) + battery) * 100) / 100;

  const sentences: string[] = [];
  if (doneNames) sentences.push(`Zrobione: ${doneNames}.`);
  let verdict: DayBudgetVerdict;
  if (remainingKwh <= 0) {
    verdict = 'ok';
    sentences.push(doneNames ? 'Nic już nie czeka na prąd.' : 'Nic nie czeka na prąd.');
  } else {
    const left = `Zostaje: ${todoNames} (ok. ${fmtKwh(remainingKwh)} kWh)`;
    if (restPv != null && remainingKwh <= restPv) {
      verdict = 'ok';
      sentences.push(`${left}, starczy słońca.`);
    } else if (restPv == null && battery <= 0) {
      verdict = 'tight';
      sentences.push(`${left}. Brak danych o prognozie i baterii.`);
    } else if (remainingKwh <= cover) {
      verdict = 'tight';
      sentences.push(`${left}, starczy słońca i baterii.`);
    } else {
      verdict = 'short';
      const gap = Math.round((remainingKwh - cover) * 100) / 100;
      sentences.push(`${left}. Do wieczora brakuje ok. ${fmtKwh(gap)} kWh, część warto przesunąć.`);
    }
  }
  if (bgPhrase) sentences.push(`W tle: ${bgPhrase}.`);

  return {
    ...base,
    verdict,
    summaryLine: sentences.join(' '),
    doneKwh,
    remainingKwh,
    progressLine: null,
    hasProgress: true,
  };
}

function buildPlanBudget(input: PlanBudgetInput): DayEnergyBudget {
  const morningLine = morningHeatLine({
    socPercent: input.socPercent ?? null,
    capacityKwh:
      input.capacityKwh != null && input.capacityKwh > 0
        ? input.capacityKwh
        : HOUSEHOLD_DEFAULT_CAPACITY_KWH,
    nightHeatKwh: input.nightHeatKwh,
    now: input.now,
  });
  const planKwh = applyMeasuredFloorHeat(
    sumPlannedEventKwh(input.eventTypes, input.extraTypes ?? []),
    input.eventTypes,
    input.extraTypes ?? [],
    input.floorHeatKwh,
  );
  const socPercent = input.socPercent ?? null;
  const reservePercent = input.reservePercent ?? 20;
  const capacityKwh =
    input.capacityKwh != null && input.capacityKwh > 0
      ? input.capacityKwh
      : HOUSEHOLD_DEFAULT_CAPACITY_KWH;
  const pvKwh =
    input.pvKwh != null && Number.isFinite(input.pvKwh) ? Math.round(input.pvKwh * 10) / 10 : null;
  const pvSource: PvBudgetSource = pvKwh != null ? input.pvSource ?? 'forecast' : null;
  const roofWord = pvSource === 'actual' ? 'produkcja' : 'prognoza';
  const batteryUsableKwh = usableBatteryKwh(socPercent, capacityKwh, reservePercent);
  const coverKwh =
    pvKwh != null
      ? Math.round((pvKwh + batteryUsableKwh) * 100) / 100
      : batteryUsableKwh > 0
        ? batteryUsableKwh
        : null;

  let verdict: DayBudgetVerdict = 'empty';
  let summaryLine = 'Zaznacz plan, a porównamy go z produkcją i baterią.';

  if (planKwh <= 0) {
    return {
      planKwh: 0,
      pvKwh,
      pvSource,
      socPercent,
      batteryUsableKwh,
      coverKwh,
      verdict,
      summaryLine,
      morningLine,
    };
  }

  if (coverKwh == null) {
    verdict = 'tight';
    summaryLine = `Plan to ok. ${fmtKwh(planKwh)} kWh. Brak danych o produkcji i baterii.`;
  } else {
    const gap = Math.round((planKwh - coverKwh) * 100) / 100;
    if (pvKwh != null && planKwh <= pvKwh) {
      verdict = 'ok';
      summaryLine =
        pvSource === 'actual'
          ? `Świetny dzień! Produkcja z dachu (${fmtKwh(pvKwh)} kWh) w pełni pokrywa dzisiejsze plany.`
          : `Świetny dzień! Prognozowana produkcja z dachu (${fmtKwh(pvKwh)} kWh) w pełni pokrywa dzisiejsze plany.`;
    } else if (planKwh <= coverKwh) {
      verdict = 'tight';
      summaryLine = `Sama ${roofWord} nie wystarczy. Razem z baterią (ok. ${fmtKwh(coverKwh)} kWh) plan powinien się zmieścić.`;
    } else {
      verdict = 'short';
      summaryLine = `Brakuje ok. ${fmtKwh(gap)} kWh względem ${roofWord === 'produkcja' ? 'produkcji' : 'prognozy'} i baterii. Część planu warto przesunąć.`;
    }
  }

  return {
    planKwh,
    pvKwh,
    pvSource,
    socPercent,
    batteryUsableKwh,
    coverKwh,
    verdict,
    summaryLine,
    morningLine,
  };
}

const FOX_FLOOR_PERCENT = 10;
const HOUSE_BASELINE_KW = 0.2;
const MORNING_HOUR = 8;

/** Czy energia powyżej 10% SoC wystarczy na nocne grzanie i tło domu do 8:00. */
export function morningHeatLine(input: {
  socPercent: number | null;
  capacityKwh: number;
  nightHeatKwh?: number | null;
  now?: Date;
}): string | null {
  const night = input.nightHeatKwh;
  if (input.socPercent == null || night == null || !Number.isFinite(night) || night <= 0) {
    return null;
  }
  const now = input.now ?? new Date();
  const hour = now.getHours() + now.getMinutes() / 60;
  let hoursUntil = MORNING_HOUR - hour;
  if (hoursUntil <= 0) hoursUntil += 24;
  if (hoursUntil < 6) return null;
  const background = Math.round(HOUSE_BASELINE_KW * hoursUntil * 10) / 10;
  const need = Math.round((night + background) * 10) / 10;
  const have = Math.round(
    Math.max(0, ((input.socPercent - FOX_FLOOR_PERCENT) / 100) * input.capacityKwh) * 10,
  ) / 10;
  const left = Math.round((have - need) * 10) / 10;
  if (left >= 0) {
    return 'Energii w baterii wystarczy do rana: grzanie i dom w tle są pokryte.';
  }
  return `Do rana potrzeba ok. ${fmtKwh(need)} kWh, głównie na ogrzewanie. W baterii jest mniej, więc ok. ${fmtKwh(-left)} kWh pójdzie z sieci.`;
}

/** Sprzęty, które mogą poczekać na lepsze słońce. Posiłki i podłogówka tu nie wchodzą. */
const PV_PLAN: Record<string, { phrase: string; hours: number }> = {
  pranie: { phrase: 'pranie', hours: 2 },
  suszarka: { phrase: 'suszarkę', hours: 1.5 },
  zmywarka: { phrase: 'zmywarkę', hours: 2 },
  piekarnik: { phrase: 'piekarnik', hours: 1.5 },
  odkurzacz: { phrase: 'Dreamy', hours: 1 },
  chleb: { phrase: 'pieczenie chleba', hours: 2 },
  przetwory: { phrase: 'przetwory', hours: 3 },
};

export interface ApplianceWindow {
  names: string;
  /** „11:00 – 14:00” */
  span: string;
}

export function dayHasPvPlan(eventTypes: readonly string[]): boolean {
  return eventTypes.some((type) => PV_PLAN[eventTypeDef(type)?.value ?? type] != null);
}

function joinPhrases(phrases: string[]): string {
  const shown = phrases.slice(0, 3);
  if (phrases.length > 3) shown[shown.length - 1] = 'inne';
  if (shown.length <= 1) return shown[0] ?? '';
  if (shown.length === 2) return `${shown[0]} i ${shown[1]}`;
  return `${shown.slice(0, -1).join(', ')} i ${shown[shown.length - 1]}`;
}

/** Podstawowe potrzeby dnia: zostają, niezależnie od słońca. */
const STAYS_TODAY: Record<string, string> = {
  sniadanie: 'śniadanie',
  obiad: 'obiad',
  kolacja: 'kolacja',
  podlogowka: 'podłogówka',
};
/** Poniżej tej sumy dnia elastyczne AGD nie jest warte trzymania na siłę. */
const WEAK_ROOF_KWH = 8;

function joinAll(phrases: string[]): string {
  if (phrases.length <= 1) return phrases[0] ?? '';
  if (phrases.length === 2) return `${phrases[0]} i ${phrases[1]}`;
  return `${phrases.slice(0, -1).join(', ')} i ${phrases[phrases.length - 1]}`;
}

function capFirst(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/**
 * Przy słabym dachu: śniadanie, obiad, kolacja i podłogówka zostają.
 * Przesunąć można tylko sprzęt, który poczeka na lepsze słońce.
 * Zwraca null, gdy dach jest mocny albo w planie nie ma czego przesunąć.
 */
export function flexibleDayLine(
  eventTypes: readonly string[],
  pvKwh: number | null,
): string | null {
  if (pvKwh == null || !Number.isFinite(pvKwh) || pvKwh >= WEAK_ROOF_KWH) return null;
  const present = new Set(eventTypes.map((type) => eventTypeDef(type)?.value ?? type));
  const stays = Object.keys(STAYS_TODAY)
    .filter((key) => present.has(key))
    .map((key) => STAYS_TODAY[key]);
  const movable = Object.keys(PV_PLAN)
    .filter((key) => present.has(key))
    .map((key) => PV_PLAN[key].phrase);
  if (!movable.length) return null;
  const moveTxt = joinPhrases(movable);
  if (!stays.length) {
    return `${capFirst(moveTxt)} możesz przełożyć na jutro — dach da dziś mało.`;
  }
  const stayVerb = stays.length > 1 ? 'zostają' : 'zostaje';
  return `Słaby dzień dla dachu. ${capFirst(joinAll(stays))} ${stayVerb} na dziś, ${moveTxt} możesz przełożyć na jutro.`;
}

/**
 * Najdłuższe sensowne okno pod plan: suma czasów urządzeń (2–5 h)
 * w ciągu dnia, tam gdzie prognoza godzinowa jest najmocniejsza.
 */
export function bestApplianceWindow(
  eventTypes: readonly string[],
  hours: ReadonlyArray<{ hour: number; predictedKwh: number }>,
  /** Najwcześniejsza godzina startu okna (dziś: pełna godzina po „teraz”). */
  fromHour = 7,
): ApplianceWindow | null {
  const planned = eventTypes
    .map((type) => PV_PLAN[eventTypeDef(type)?.value ?? type])
    .filter((row): row is { phrase: string; hours: number } => row != null);
  if (!planned.length || !hours.length) return null;
  const phrases: string[] = [];
  for (const row of planned) {
    if (!phrases.includes(row.phrase)) phrases.push(row.phrase);
  }
  const spanHours = Math.min(5, Math.max(2, Math.ceil(planned.reduce((sum, row) => sum + row.hours, 0))));
  const byHour = new Map<number, number>();
  for (const row of hours) {
    if (Number.isFinite(row.predictedKwh)) byHour.set(row.hour, row.predictedKwh);
  }
  let bestStart = -1;
  let bestScore = 0;
  for (let start = Math.max(7, fromHour); start <= 20 - spanHours; start += 1) {
    let score = 0;
    for (let hour = start; hour < start + spanHours; hour += 1) {
      score += byHour.get(hour) ?? 0;
    }
    if (score > bestScore) {
      bestScore = score;
      bestStart = start;
    }
  }
  if (bestStart < 0 || bestScore < spanHours * 0.6) return null;
  const end = bestStart + spanHours;
  const clock = (hour: number) => `${String(hour).padStart(2, '0')}:00`;
  return {
    names: joinPhrases(phrases),
    span: `${clock(bestStart)} – ${clock(end)}`,
  };
}

/* —— Początek i czas programu AGD —— */

export type EventProgressState = 'done' | 'running' | 'planned' | 'pending' | 'background';

export interface EventTimes {
  event_date: string;
  /** Typ ikony — dla Mac mini / MacBooka / podłogówki bez godzin status to „w tle”. */
  event_type?: string;
  start_time?: string | null;
  duration_min?: number | null;
  planned_time?: string | null;
}

export interface EventProgress {
  state: EventProgressState;
  /** HH:MM, gdy ruszyło (albo ma ruszyć o podanej godzinie). */
  startLabel: string | null;
  /** HH:MM końca programu, gdy znamy start i czas. */
  endLabel: string | null;
  plannedLabel: string | null;
  /** Krótki opis pod nazwą ikony. */
  caption: string;
}

/** „13:32” → minuty od północy. Zły format → null. */
export function parseClock(value: string | null | undefined): number | null {
  const match = /^([01]?\d|2[0-3]):([0-5]\d)$/.exec((value ?? '').trim());
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

export function fmtClock(minutes: number): string {
  const wrapped = ((Math.round(minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(wrapped / 60)).padStart(2, '0')}:${String(wrapped % 60).padStart(2, '0')}`;
}

/** 138 → „2 h 18 min”. */
export function fmtDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes));
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h && m) return `${h} h ${m} min`;
  return h ? `${h} h` : `${m} min`;
}

function isoOfLocal(now: Date): string {
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${m}-${d}`;
}

/**
 * Czy dana czynność już pobrała prąd. Wcześniejsze dni = zrobione, kolejne = przed Tobą.
 * Dziś rozstrzyga start_time i czas programu; bez startu czynność dopiero czeka.
 */
export function eventProgress(event: EventTimes, now: Date = new Date()): EventProgress {
  const today = isoOfLocal(now);
  const startMin = parseClock(event.start_time);
  const duration = event.duration_min != null && event.duration_min > 0 ? event.duration_min : null;
  const plannedMin = parseClock(event.planned_time);
  const startLabel = startMin != null ? fmtClock(startMin) : null;
  const endLabel = startMin != null && duration != null ? fmtClock(startMin + duration) : null;
  const plannedLabel = plannedMin != null ? fmtClock(plannedMin) : null;
  const done = (caption: string): EventProgress => ({ state: 'done', startLabel, endLabel, plannedLabel, caption });

  // Praca w tle bez własnych godzin: zawsze „pracuje w tle”, także w innych dniach.
  if (isBackgroundType(event.event_type) && startMin == null && plannedMin == null) {
    return { state: 'background', startLabel, endLabel, plannedLabel, caption: 'pracuje w tle' };
  }

  if (event.event_date < today) {
    return done(startLabel ? (endLabel ? `${startLabel}–${endLabel}` : `od ${startLabel}`) : 'zrobione');
  }

  const nowMin = now.getHours() * 60 + now.getMinutes();
  if (event.event_date === today && startMin != null && startMin <= nowMin) {
    if (duration != null && nowMin < startMin + duration) {
      return {
        state: 'running',
        startLabel,
        endLabel,
        plannedLabel,
        caption: `trwa do ${endLabel}`,
      };
    }
    return done(endLabel ? `${startLabel}–${endLabel}` : `od ${startLabel}`);
  }

  // Start wpisany na później (dziś albo kolejny dzień) = to samo, co planowana godzina.
  const when = startLabel ?? plannedLabel;
  if (when) {
    return { state: 'planned', startLabel, endLabel, plannedLabel, caption: `plan ${when}` };
  }
  return { state: 'pending', startLabel, endLabel, plannedLabel, caption: 'jeszcze nie' };
}

/** Dla dzisiejszych wpisów: co już pobrało prąd (zrobione + trwa), a co jeszcze nie. */
export function splitDayProgress(
  events: ReadonlyArray<EventTimes & { event_type: string }>,
  now: Date = new Date(),
): { done: string[]; running: string[]; todo: string[] } {
  const out = { done: [] as string[], running: [] as string[], todo: [] as string[] };
  for (const event of events) {
    const { state } = eventProgress(event, now);
    if (state === 'done') out.done.push(event.event_type);
    else if (state === 'running' || state === 'background') out.running.push(event.event_type);
    else out.todo.push(event.event_type);
  }
  return out;
}
