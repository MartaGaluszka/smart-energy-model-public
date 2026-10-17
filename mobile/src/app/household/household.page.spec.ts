import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { AlertController, ToastController } from '@ionic/angular';
import { of, throwError } from 'rxjs';
import { ApiService, HouseholdEventDto } from '../services/api.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { HouseholdPage } from './household.page';
import { applyMeasuredFloorHeat, buildDayEnergyBudget, customTypeDef, dayAdvisorLine, morningHeatLine, tintForEstimatedKwh } from './household.types';

describe('HouseholdPage (Rytm domu)', () => {
  let fixture: ComponentFixture<HouseholdPage>;
  let component: HouseholdPage;
  let api: jasmine.SpyObj<ApiService>;

  const sample: HouseholdEventDto[] = [
    {
      id: 1,
      event_date: todayIsoLocal(),
      event_type: 'pranie',
      impact: 'up',
      note: null,
    },
  ];

  beforeEach(async () => {
    api = jasmine.createSpyObj('ApiService', [
      'getHouseholdEvents',
      'getHouseholdCustomTypes',
      'getFloorHeat',
      'createHouseholdEvent',
      'createHouseholdCustomType',
      'deleteHouseholdCustomType',
      'deleteHouseholdEvent',
      'getForecastHourly',
      'getFoxOverview',
      'getBatterySettings',
      'getBatterySuggestion',
    ]);
    api.getHouseholdEvents.and.returnValue(of(sample));
    api.getHouseholdCustomTypes.and.returnValue(of([]));
    api.getFloorHeat.and.returnValue(of([]));
    api.createHouseholdEvent.and.returnValue(
      of({
        id: 2,
        event_date: todayIsoLocal(),
        event_type: 'suszarka',
        impact: 'up',
        note: null,
      }),
    );
    api.deleteHouseholdEvent.and.returnValue(of(void 0));
    api.getForecastHourly.and.returnValue(
      of({ day: todayIsoLocal(), hours: [], total_kwh: 18, model_path: '' }),
    );
    api.getFoxOverview.and.returnValue(
      of({
        day: todayIsoLocal(),
        pv_kwh: 27.5,
        soc_percent: 79,
        grid_import_kwh: 0,
        grid_export_kwh: 0,
        load_kwh: 0,
        device_sn_display: 'x',
        last_synced_at: null,
        has_data: true,
      }),
    );
    api.getBatterySettings.and.returnValue(
      of({
        battery_capacity_kwh: 10.36,
        soc_reserve_percent: 22,
      } as any),
    );
    api.getBatterySuggestion.and.returnValue(
      of({ soc_now_percent: 79, soc_reserve_percent: 22 } as any),
    );

    await TestBed.configureTestingModule({
      declarations: [HouseholdPage],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [
        { provide: ApiService, useValue: api },
        {
          provide: AlertController,
          useValue: {
            create: jasmine.createSpy('create').and.resolveTo({
              present: jasmine.createSpy('present'),
            }),
          },
        },
        {
          provide: ToastController,
          useValue: {
            create: jasmine.createSpy('create').and.resolveTo({
              present: jasmine.createSpy('present'),
            }),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HouseholdPage);
    component = fixture.componentInstance;
  });

  it('loads a 7-day rhythm with week strip, hero and axis', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    fixture.detectChanges();

    expect(api.getHouseholdEvents).toHaveBeenCalled();
    const [from, to] = api.getHouseholdEvents.calls.mostRecent().args;
    expect(from).toBe(todayIsoLocal());
    expect(to).toBe(shiftIsoDate(todayIsoLocal(), 6));
    expect(component.days.length).toBe(7);
    expect(component.focusDayIso).toBe(todayIsoLocal());
    expect(component.focusDay?.events[0].event_type).toBe('pranie');
    expect(component.focusDay?.advisorLine).toContain('Pranie');
    expect(component.focusBudget?.planKwh).toBe(1.5);
    expect(component.focusBudget?.pvKwh).toBe(27.5);
    expect(component.focusBudget?.pvSource).toBe('actual');
    expect(component.focusBudget?.socPercent).toBe(79);
    expect(component.focusBudget?.verdict).toBe('ok');
    expect(api.getForecastHourly).not.toHaveBeenCalled();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="rhythm-budget"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="rhythm-week"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="rhythm-hero"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="rhythm-axis"]')).toBeTruthy();
    expect(el.querySelectorAll('.se-rhythm-week__cell').length).toBe(7);
    expect(el.textContent).toContain('Rytm domu');
    expect(el.textContent).not.toContain('7 dni');
  }));

  it('uses the forecast label from tomorrow onward', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    const tomorrow = shiftIsoDate(todayIsoLocal(), 1);
    component.selectDay(tomorrow);
    tick();
    expect(api.getForecastHourly).toHaveBeenCalledWith(tomorrow);
    expect(component.focusBudget?.pvSource).toBe('forecast');
    expect(component.focusBudget?.pvKwh).toBe(18);
  }));

  it('selectDay focuses another day on the strip', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    const other = shiftIsoDate(todayIsoLocal(), 2);
    component.selectDay(other);
    fixture.detectChanges();
    expect(component.focusDayIso).toBe(other);
    expect(component.focusDay?.dayIso).toBe(other);
    expect(component.timelineDays.every((d) => d.dayIso !== other)).toBe(true);
  }));

  it('creates an event and shows insight toast with szacunek', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    component.openAdd(todayIsoLocal());
    component.formTypes = ['pranie'];
    component.save();
    tick();
    fixture.detectChanges();

    expect(api.createHouseholdEvent).toHaveBeenCalled();
    expect(component.insightBanner).toContain('Dzięki zaznaczeniu');
    expect(component.insightBanner).toContain('Szacunek');
    expect(component.insightBanner).toContain('zł');
    expect(fixture.nativeElement.querySelector('[data-testid="rhythm-insight"]')).toBeTruthy();
  }));

  it('toggles multi-select and saves several types at once', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    component.openAdd(todayIsoLocal());
    component.formTypes = [];
    component.toggleType('pranie');
    component.toggleType('suszarka');
    component.toggleType('zmywarka');
    expect(component.formTypes).toEqual(['pranie', 'suszarka', 'zmywarka']);
    expect(component.saveLabel).toBe('Zapisz (3)');
    component.save();
    tick();
    expect(api.createHouseholdEvent).toHaveBeenCalledTimes(3);
    expect(component.insightBanner).toContain('Pranie');
    expect(component.insightBanner).toContain('Suszarka');
  }));

  it('stacks another entry for any type on second tap', () => {
    component.formTypes = [];
    component.toggleType('zmywarka');
    component.toggleType('zmywarka');
    component.toggleType('wyjazd');
    component.toggleType('wyjazd');
    expect(component.formTypes).toEqual(['zmywarka', 'zmywarka', 'wyjazd', 'wyjazd']);
    expect(component.countOfType('wyjazd')).toBe(2);
    component.removeOneType('wyjazd');
    expect(component.countOfType('wyjazd')).toBe(1);
  });

  it('laundry scenario preselects pranie + suszarka', () => {
    const laundry = component.scenarios.find((s) => s.id === 'laundry')!;
    component.pickScenario(laundry);
    expect(component.formTypes).toEqual(['pranie', 'suszarka']);
    expect(component.isScenarioActive(laundry)).toBe(true);
  });

  it('exposes scenarios and full type catalog with meals first', () => {
    expect(component.scenarios.map((s) => s.id)).toEqual(['laundry', 'heat', 'away', 'floor']);
    const values = component.typeCatalog.map((t) => t.value);
    expect(values.slice(0, 10)).toEqual([
      'sniadanie',
      'obiad',
      'kolacja',
      'zmywarka',
      'chleb',
      'piekarnik',
      'grzejnik_lazienka',
      'podlogowka',
      'pranie',
      'suszarka',
    ]);
    expect(component.typeCatalog.find((t) => t.value === 'chleb')?.icon).toBe('se-bread');
    expect(component.typeCatalog.find((t) => t.value === 'piekarnik')?.icon).toBe('se-oven');
    expect(component.typeCatalog.find((t) => t.value === 'piekarnik')?.estimatedKwh).toBe(2);
    expect(component.typeCatalog.find((t) => t.value === 'odkurzacz')?.icon).toBe('se-robot');
    expect(component.typeCatalog.find((t) => t.value === 'odkurzacz')?.estimatedKwh).toBe(0.2);
    expect(component.typeCatalog.find((t) => t.value === 'odkurzacz')?.tint).toBe('moss');
    expect(component.typeCatalog.find((t) => t.value === 'mac_mini')?.estimatedKwh).toBe(0.2);
    expect(component.typeCatalog.find((t) => t.value === 'macbook')?.estimatedKwh).toBe(1.12);
    expect(component.typeCatalog.find((t) => t.value === 'macbook')?.tint).toBe('moss');
    expect(component.typeCatalog.find((t) => t.value === 'pranie')?.icon).toBe('se-washer');
    expect(component.typeCatalog.find((t) => t.value === 'sniadanie')?.icon).toBe('se-breakfast');
    expect(component.typeCatalog.find((t) => t.value === 'obiad')?.icon).toBe('se-utensils');
    expect(component.typeCatalog.find((t) => t.value === 'kolacja')?.icon).toBe('se-plate');
    expect(component.typeCatalog.find((t) => t.value === 'zmywarka')?.icon).toBe('se-dishwasher');
    expect(component.typeCatalog.find((t) => t.value === 'podlogowka')?.icon).toBe('se-floor-heat');
  });

  it('surfaces save error inside the sheet when API fails', fakeAsync(() => {
    api.createHouseholdEvent.and.returnValue(throwError(() => new Error('net')));
    fixture.detectChanges();
    tick();
    component.openAdd(todayIsoLocal());
    component.formTypes = ['pranie'];
    component.save();
    tick();
    fixture.detectChanges();
    expect(component.showAdd).toBe(true);
    expect(component.formError).toBeTruthy();
    expect(fixture.nativeElement.querySelector('[data-testid="form-save-error"]')).toBeTruthy();
  }));

  it('buildDayEnergyBudget flags a short day when icons exceed forecast and battery', () => {
    const budget = buildDayEnergyBudget({
      eventTypes: ['pranie', 'suszarka', 'przetwory'],
      pvKwh: 5,
      socPercent: 30,
      capacityKwh: 10.36,
      reservePercent: 20,
    });
    expect(budget.planKwh).toBeGreaterThan(10);
    expect(budget.verdict).toBe('short');
    expect(budget.summaryLine).toContain('Brakuje');
  });

  it('counts a custom tile in the day budget and paints a heavy load red', () => {
    const def = customTypeDef({ id: 3, label: 'Ładowanie auta', icon: 'car-outline', kwh: 12 });
    expect(tintForEstimatedKwh(12)).toBe('cost');
    expect(tintForEstimatedKwh(0.2)).toBe('moss');
    const budget = buildDayEnergyBudget({
      eventTypes: ['c3'],
      extraTypes: [def],
      pvKwh: 5,
      socPercent: 20,
      capacityKwh: 10,
      reservePercent: 20,
    });
    expect(budget.planKwh).toBe(12);
    expect(dayAdvisorLine(['c3'], [def])).toContain('Ładowanie auta');
  });

  it('replaces the floor-heat catalog kWh with the measured Fox total', () => {
    expect(applyMeasuredFloorHeat(2.6, ['sniadanie', 'podlogowka'], [], 3.6)).toBe(5);
    expect(applyMeasuredFloorHeat(2.6, ['sniadanie', 'podlogowka'], [], null)).toBe(2.6);
    const budget = buildDayEnergyBudget({
      eventTypes: ['sniadanie', 'podlogowka', 'podlogowka'],
      floorHeatKwh: 3.6,
    });
    expect(budget.planKwh).toBe(5);
  });

  it('says whether the battery covers a night of floor heat until morning', () => {
    const evening = new Date(2026, 9, 17, 17, 0, 0);
    const enough = morningHeatLine({
      socPercent: 90,
      capacityKwh: 10.36,
      nightHeatKwh: 3.1,
      now: evening,
    });
    expect(enough).toContain('Bilans nocny na plus');
    const short = morningHeatLine({
      socPercent: 40,
      capacityKwh: 10.36,
      nightHeatKwh: 3.1,
      now: evening,
    });
    expect(short).toContain('Brakuje');
    expect(morningHeatLine({ socPercent: 90, capacityKwh: 10.36, nightHeatKwh: 0, now: evening })).toBeNull();
  });

  it('dayAdvisorLine distinguishes laundry vs empty', () => {
    expect(dayAdvisorLine(['pranie'])).toContain('Pranie');
    expect(dayAdvisorLine([])).toContain('Zaznacz plan');
  });

  it('shows error state when API fails but still builds empty days', fakeAsync(() => {
    api.getHouseholdEvents.and.returnValue(throwError(() => new Error('net')));
    fixture.detectChanges();
    tick();
    expect(component.error).toContain('Nie udało się');
    expect(component.days.length).toBe(7);
  }));
});
