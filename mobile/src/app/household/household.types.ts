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
    return 'Pranie w planie — przy dobrym PV wieczorem pomiń nocne FC.';
  }
  if (keys.includes('kolacja')) {
    return 'Kolacja jak śniadanie (~1,3–1,4 kWh) — czajnik/piekarnik z baterii; pilnuj SoC przed 22.';
  }
  if (keys.includes('klimatyzacja')) {
    return 'Upał w kalendarzu — na Home pojawi się sugestia wyłączenia AC.';
  }
  if (keys.includes('wyjazd') || keys.includes('ferie')) {
    return 'Wyjazd — łagodniejszy bufor, bez dokręcania SoC na zapas.';
  }
  if (keys.includes('przetwory')) {
    return 'Przetwory — następny dzień pilnuj SoC przed 22.';
  }
  if (keys.includes('grzejnik_lazienka')) {
    return 'Grzejnik łazienka — +~0,75 kWh do budżetu nocy.';
  }
  if (keys.includes('podlogowka')) {
    return 'Podłogówka — system szacuje kWh nocy z temperatury i cel SoC przed 22.';
  }
  if (keys.includes('sniadanie')) {
    return 'Śniadanie zaznaczone — wliczone w bufor rano.';
  }
  if (keys.includes('obiad')) {
    return 'Obiad w planie — krótkie piki; najlepiej przy PV / pełnej baterii.';
  }
  if (keys.length) {
    const first = eventTypeDef(keys[0]);
    return first?.insightHint ?? 'Doradca baterii uwzględni ten dzień.';
  }
  return 'Zaznacz plan dnia — doradca dopasuje sugestię baterii.';
}
