/** Katalog typów kalendarza — zgodny z PROJEKT §10.1. */
export type HouseholdImpact = 'up' | 'down' | 'neutral';

export interface HouseholdEventTypeDef {
  value: string;
  label: string;
  /** Krótka etykieta w gęstej siatce modału (opcjonalnie). */
  shortLabel?: string;
  icon: string;
  /** Klasa tła chipa (SCSS). */
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
    estimatedKwh: 1,
    insightHint: 'Krótki pik — OK przy pełnej baterii i PV (szczyt dnia).',
  },
  {
    value: 'kolacja',
    label: 'Kolacja',
    icon: 'se-plate',
    tint: 'cost',
    defaultImpact: 'up',
    estimatedKwh: 1.4,
    insightHint:
      'Jak śniadanie ~1,3–1,4 kWh (ciepłe + czajnik / piekarnik) — wieczór bez PV, pilnuj SoC przed 22.',
  },
  {
    value: 'zmywarka',
    label: 'Zmywarka',
    icon: 'se-dishwasher',
    tint: 'grid',
    defaultImpact: 'up',
    estimatedKwh: 1.2,
    insightHint: 'Szczyt PV albo tania 13–15 / po 22.',
  },
  {
    value: 'chleb',
    label: 'Pieczenie chleba',
    shortLabel: 'Chleb',
    icon: 'se-bread',
    tint: 'muted',
    defaultImpact: 'up',
    estimatedKwh: 0.8,
    insightHint: 'Lekkie obciążenie — można równolegle z innym AGD.',
  },
  {
    value: 'grzejnik_lazienka',
    label: 'Grzejnik łazienka',
    shortLabel: 'Grzejnik',
    icon: 'se-radiator',
    tint: 'cost',
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
    tint: 'grid',
    defaultImpact: 'up',
    estimatedKwh: 1.5,
    insightHint: 'Najlepiej w szczycie PV; przy słońcu pomiń nocne FC.',
  },
  {
    value: 'suszarka',
    label: 'Suszarka',
    icon: 'se-dryer',
    tint: 'cost',
    defaultImpact: 'up',
    estimatedKwh: 1.2,
    insightHint: 'Po praniu; cykl ~1–1,5 kWh przy SoC wysokim — wieczorem z baterii.',
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
    tint: 'solar',
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
export function dayAdvisorLine(eventTypes: string[]): string {
  const keys = eventTypes.map((t) => eventTypeDef(t)?.value ?? t);
  if (keys.includes('pranie')) {
    return 'Pranie jest w planie. Przy dobrej produkcji z dachu wieczorne ładowanie z sieci nie będzie potrzebne.';
  }
  if (keys.includes('kolacja')) {
    return 'Kolacja zużywa podobną ilość energii jak śniadanie. Wieczorem instalacja już nie produkuje, więc przed 22 warto sprawdzić stan baterii.';
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
    return 'Obiad to krótki wzrost zużycia. Najkorzystniej uruchomić go przy produkcji z dachu albo przy pełnej baterii.';
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
}

export function fmtKwh(n: number): string {
  const rounded = Math.round(n * 10) / 10;
  return (Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)).replace('.', ',');
}

/** Suma szacunków kWh z katalogu (wyjazd / ferie = 0). */
export function sumPlannedEventKwh(eventTypes: string[]): number {
  let sum = 0;
  for (const t of eventTypes) {
    const def = eventTypeDef(t);
    if (def && def.estimatedKwh > 0 && def.defaultImpact !== 'down') {
      sum += def.estimatedKwh;
    }
  }
  return Math.round(sum * 100) / 100;
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

/** Czy plan ikon mieści się w prognozie dnia i energii z baterii powyżej rezerwy. */
export function buildDayEnergyBudget(input: {
  eventTypes: string[];
  pvKwh?: number | null;
  pvSource?: PvBudgetSource;
  socPercent?: number | null;
  capacityKwh?: number | null;
  reservePercent?: number | null;
}): DayEnergyBudget {
  const planKwh = sumPlannedEventKwh(input.eventTypes);
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
          ? `Dzisiejsza produkcja (ok. ${fmtKwh(pvKwh)} kWh) pokrywa plan.`
          : `Prognoza (ok. ${fmtKwh(pvKwh)} kWh) pokrywa plan. Urządzenia najlepiej włączyć w godzinach największej produkcji.`;
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
  };
}
