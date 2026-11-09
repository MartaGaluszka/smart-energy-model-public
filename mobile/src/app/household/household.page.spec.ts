import { CommonModule } from '@angular/common';
import { CUSTOM_ELEMENTS_SCHEMA, Component, ContentChild, Input, TemplateRef } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AlertController, ToastController } from '@ionic/angular';
import { of, throwError } from 'rxjs';
import { ApiService, HouseholdEventDto } from '../services/api.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { HouseholdPage } from './household.page';
import { applyMeasuredFloorHeat, bestApplianceWindow, buildDayEnergyBudget, customTypeDef, dayAdvisorLine, eventProgress, flexibleDayLine, morningHeatLine, splitDayProgress, tintForEstimatedKwh } from './household.types';

/** `ion-modal` bez Ionic Core: pokazuje szablon dopiero, gdy `isOpen` — jak w apce. */
@Component({
  selector: 'ion-modal',
  template: '<ng-container *ngIf="isOpen && body"><ng-container *ngTemplateOutlet="body"></ng-container></ng-container>',
  standalone: false,
})
class IonModalStubComponent {
  @Input() isOpen = false;
  @ContentChild(TemplateRef) body?: TemplateRef<unknown>;
}

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
      'updateHouseholdEventTimes',
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
      imports: [CommonModule, FormsModule],
      declarations: [HouseholdPage, IonModalStubComponent],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [
        { provide: ApiService, useValue: api },
        { provide: Router, useValue: { navigate: jasmine.createSpy('navigate') } },
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
    // Dziś pranie jeszcze nie ruszyło: werdykt liczy tylko to, co zostało (bateria powyżej rezerwy).
    expect(component.focusBudget?.hasProgress).toBe(true);
    expect(component.focusBudget?.doneKwh).toBe(0);
    expect(component.focusBudget?.remainingKwh).toBe(1.5);
    expect(component.focusBudget?.verdict).toBe('tight');
    expect(api.getForecastHourly).toHaveBeenCalledWith(todayIsoLocal());

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
    component.formTypes = ['pranie', 'suszarka'];
    component.save();
    tick();
    fixture.detectChanges();

    expect(api.createHouseholdEvent).toHaveBeenCalled();
    expect(component.insightBanner).toContain('Dzięki zaznaczeniu');
    expect(component.insightBanner).toContain('Szacowany koszt');
    expect(component.insightBanner).toContain('zł');
    expect(fixture.nativeElement.querySelector('[data-testid="rhythm-insight"]')).toBeTruthy();
  }));

  it('toggles multi-select and saves several types at once', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    component.openAdd(shiftIsoDate(todayIsoLocal(), 1));
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

  it('opens Plan dnia with that day’s tiles, or none when the day is empty', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    component.openAdd(todayIsoLocal());
    expect(component.formTypes).toEqual(['pranie']);
    component.openAdd(shiftIsoDate(todayIsoLocal(), 1));
    expect(component.formTypes).toEqual([]);
  }));

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
    component.formTypes = ['suszarka'];
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
    expect(enough).toContain('wystarczy do rana');
    const short = morningHeatLine({
      socPercent: 40,
      capacityKwh: 10.36,
      nightHeatKwh: 3.1,
      now: evening,
    });
    expect(short).toContain('pójdzie z sieci');
    expect(morningHeatLine({ socPercent: 90, capacityKwh: 10.36, nightHeatKwh: 0, now: evening })).toBeNull();
  });

  it('picks the sunniest hours for laundry', () => {
    const window = bestApplianceWindow(
      ['pranie', 'suszarka'],
      [
        { hour: 9, predictedKwh: 0.4 },
        { hour: 10, predictedKwh: 1.2 },
        { hour: 11, predictedKwh: 3.8 },
        { hour: 12, predictedKwh: 4.1 },
        { hour: 13, predictedKwh: 3.2 },
        { hour: 14, predictedKwh: 1.1 },
        { hour: 15, predictedKwh: 0.3 },
      ],
    );
    expect(window?.names).toBe('pranie i suszarkę');
    expect(window?.span).toBe('10:00 – 14:00');
    expect(bestApplianceWindow(['sniadanie'], [{ hour: 12, predictedKwh: 4 }])).toBeNull();
  });

  it('keeps the meal and offers to move laundry on a weak roof', () => {
    expect(flexibleDayLine(['obiad', 'pranie'], 5)).toBe(
      'Słaby dzień dla dachu. Obiad zostaje na dziś, pranie możesz przełożyć na jutro.',
    );
    expect(flexibleDayLine(['kolacja', 'sniadanie', 'podlogowka', 'zmywarka'], 4)).toBe(
      'Słaby dzień dla dachu. Śniadanie, kolacja i podłogówka zostają na dziś, zmywarkę możesz przełożyć na jutro.',
    );
    expect(flexibleDayLine(['obiad', 'pranie'], 18)).toBeNull();
    expect(flexibleDayLine(['sniadanie', 'obiad', 'kolacja', 'podlogowka'], 4)).toBeNull();
    expect(flexibleDayLine(['pranie', 'suszarka'], 3)).toContain('przełożyć na jutro');
    expect(bestApplianceWindow(['obiad', 'sniadanie', 'kolacja'], [{ hour: 12, predictedKwh: 4 }])).toBeNull();
  });

  it('Jak wczoraj copies the previous day tiles into the sheet', () => {
    const today = todayIsoLocal();
    const yesterday = shiftIsoDate(today, -1);
    component.formDate = today;
    component.events = [
      { id: 1, event_date: yesterday, event_type: 'obiad', impact: 'up', note: null },
      { id: 2, event_date: yesterday, event_type: 'zmywarka', impact: 'up', note: null },
    ];
    expect(component.previousDayLabel).toBe('Jak wczoraj');
    component.pickPreviousDay();
    expect(component.formTypes).toEqual(['obiad', 'zmywarka']);
    expect(component.isPreviousDayActive()).toBe(true);
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
  describe('początek i czas programu AGD', () => {
    const now = new Date(2026, 10, 9, 13, 37);
    const day = '2026-11-09';

    it('eventProgress: skończone, trwa, jeszcze nie i planowane', () => {
      const done = eventProgress({ event_date: day, start_time: '10:47', duration_min: 138 }, now);
      expect(done.state).toBe('done');
      expect(done.caption).toBe('10:47–13:05');

      const running = eventProgress({ event_date: day, start_time: '13:32', duration_min: 127 }, now);
      expect(running.state).toBe('running');
      expect(running.endLabel).toBe('15:39');
      expect(running.caption).toBe('trwa do 15:39');

      expect(eventProgress({ event_date: day, start_time: '10:11' }, now).state).toBe('done');
      expect(eventProgress({ event_date: day }, now)).toEqual(
        jasmine.objectContaining({ state: 'pending', caption: 'jeszcze nie' }),
      );
      const planned = eventProgress({ event_date: day, planned_time: '18:00' }, now);
      expect(planned.state).toBe('planned');
      expect(planned.caption).toBe('plan 18:00');
    });

    it('eventProgress: start wpisany na później to jeszcze plan; wcześniejsze dni zrobione, kolejne czekają', () => {
      expect(eventProgress({ event_date: day, start_time: '15:00' }, now).state).toBe('planned');
      expect(eventProgress({ event_date: '2026-11-08' }, now).state).toBe('done');
      expect(eventProgress({ event_date: '2026-11-10' }, now).state).toBe('pending');
      expect(eventProgress({ event_date: '2026-11-10', planned_time: '09:30' }, now).caption).toBe('plan 09:30');
    });

    it('splitDayProgress dzieli dzień na zrobione, trwa i do zrobienia', () => {
      const split = splitDayProgress(
        [
          { event_date: day, event_type: 'zmywarka', start_time: '10:47', duration_min: 138 },
          { event_date: day, event_type: 'suszarka', start_time: '13:32', duration_min: 127 },
          { event_date: day, event_type: 'pranie' },
        ],
        now,
      );
      expect(split).toEqual({ done: ['zmywarka'], running: ['suszarka'], todo: ['pranie'] });
    });

    it('budżet dnia: komunikat mówi, co już pobrało prąd, a co jeszcze nie', () => {
      const budget = buildDayEnergyBudget({
        eventTypes: ['zmywarka', 'pranie'],
        pvKwh: 20,
        socPercent: 60,
        capacityKwh: 10,
        reservePercent: 20,
        progress: { done: ['zmywarka'], todo: ['pranie'], remainingPvKwh: 6 },
      });
      expect(budget.hasProgress).toBe(true);
      expect(budget.doneKwh).toBe(1.2);
      expect(budget.remainingKwh).toBe(1.5);
      expect(budget.summaryLine).toContain('Zrobione: zmywarka.');
      expect(budget.summaryLine).toContain('Zostaje: pranie (ok. 1,5 kWh), starczy słońca.');
      expect(budget.verdict).toBe('ok');
    });

    it('budżet dnia: gdy wszystko zrobione, nic już nie czeka na prąd', () => {
      const budget = buildDayEnergyBudget({
        eventTypes: ['zmywarka'],
        pvKwh: 3,
        socPercent: 30,
        capacityKwh: 10,
        progress: { done: ['zmywarka'], todo: [], remainingPvKwh: 0 },
      });
      expect(budget.remainingKwh).toBe(0);
      expect(budget.verdict).toBe('ok');
      expect(budget.summaryLine).toContain('Nic już nie czeka na prąd.');
      expect(budget.summaryLine).not.toContain('Zostaje');
    });

    it('budżet dnia: brak słońca i baterii na to, co zostało, to „short”', () => {
      const budget = buildDayEnergyBudget({
        eventTypes: ['pranie', 'suszarka'],
        pvKwh: 10,
        socPercent: 20,
        capacityKwh: 10,
        reservePercent: 20,
        progress: { done: [], todo: ['pranie', 'suszarka'], remainingPvKwh: 0.5 },
      });
      expect(budget.verdict).toBe('short');
      expect(budget.summaryLine).toContain('Do wieczora brakuje');
      expect(budget.summaryLine).toContain('część warto przesunąć');
    });

    it('Mac mini, MacBook i podłogówka bez godzin pracują w tle i nie są „do zrobienia”', () => {
      const now = new Date(2026, 10, 9, 13, 37);
      for (const type of ['mac_mini', 'macbook', 'podlogowka']) {
        const progress = eventProgress({ event_date: '2026-11-09', event_type: type }, now);
        expect(progress.state).toBe('background');
        expect(progress.caption).toBe('pracuje w tle');
      }
      // Własne godziny mają pierwszeństwo.
      expect(
        eventProgress({ event_date: '2026-11-09', event_type: 'macbook', start_time: '09:00', duration_min: 60 }, now).state,
      ).toBe('done');
      const split = splitDayProgress(
        [
          { event_date: '2026-11-09', event_type: 'mac_mini' },
          { event_date: '2026-11-09', event_type: 'pranie' },
        ],
        now,
      );
      expect(split.todo).toEqual(['pranie']);
      expect(split.running).toEqual(['mac_mini']);
    });

    it('budżet dnia: urządzenia w tle liczą się jako zużyte, nie jako „zostało”', () => {
      const budget = buildDayEnergyBudget({
        eventTypes: ['mac_mini', 'macbook', 'pranie'],
        pvKwh: 10,
        socPercent: 60,
        capacityKwh: 10,
        reservePercent: 20,
        progress: { done: ['mac_mini', 'macbook'], todo: ['pranie'], remainingPvKwh: 5 },
      });
      expect(budget.remainingKwh).toBe(1.5);
      expect(budget.doneKwh).toBe(1.32);
      expect(budget.summaryLine).toContain('W tle: komputery.');
      expect(budget.summaryLine).not.toContain('Zrobione');
      expect(budget.summaryLine).toContain('Zostaje: pranie');
    });

    it('„Już zużyte” to pomiar z falownika, „Jeszcze w planie” to szacunek z ikon', () => {
      const budget = buildDayEnergyBudget({
        eventTypes: ['zmywarka', 'pranie'],
        pvKwh: 21.1,
        pvSource: 'actual',
        socPercent: 71,
        capacityKwh: 10,
        reservePercent: 20,
        loadKwh: 19.9,
        progress: { done: ['zmywarka'], todo: ['pranie'], remainingPvKwh: 3 },
      });
      expect(budget.doneKwh).toBe(19.9);
      expect(budget.remainingKwh).toBe(1.5);
    });

    it('harmonogram: gdy słońca nie starcza, a bateria pomaga; gdy komputery i podłogówka w tle', () => {
      const tight = buildDayEnergyBudget({
        eventTypes: ['kolacja', 'mac_mini', 'macbook', 'podlogowka', 'obiad'],
        pvKwh: 20,
        socPercent: 71,
        capacityKwh: 10.36,
        reservePercent: 20,
        progress: { done: ['obiad', 'mac_mini', 'macbook', 'podlogowka'], todo: ['kolacja'], remainingPvKwh: 0.5 },
      });
      expect(tight.verdict).toBe('tight');
      expect(tight.summaryLine).toBe(
        'Zrobione: obiad. Zostaje: kolacja (ok. 1,4 kWh), starczy słońca i baterii. W tle: komputery i podłogówka.',
      );
    });

    it('bohater pokazuje stan ikony: zrobione z godzinami, jeszcze nie', fakeAsync(() => {
      api.getHouseholdEvents.and.returnValue(
        of([
          { id: 1, event_date: todayIsoLocal(), event_type: 'zmywarka', impact: 'up', note: null, start_time: '00:00', duration_min: 1 },
          { id: 2, event_date: todayIsoLocal(), event_type: 'pranie', impact: 'up', note: null },
        ]),
      );
      fixture.detectChanges();
      tick();
      fixture.detectChanges();
      const chips = Array.from(
        (fixture.nativeElement as HTMLElement).querySelectorAll('[data-testid="rhythm-chip"]'),
      );
      expect(chips.map((c) => c.getAttribute('data-state'))).toEqual(['done', 'pending']);
      expect(chips[0].textContent).toContain('00:00–00:01');
      expect(chips[1].textContent).toContain('jeszcze nie');
      expect((fixture.nativeElement as HTMLElement).querySelector('[data-testid="rhythm-schedule"]')?.textContent)
        .toContain('Zrobione: zmywarka.');
    }));

    it('skrót do Prognozy jest zawsze, także gdy nie ma okna na AGD', fakeAsync(() => {
      fixture.detectChanges();
      tick();
      component.focusWindow = null;
      fixture.detectChanges();
      const link = (fixture.nativeElement as HTMLElement).querySelector(
        '[data-testid="rhythm-forecast-link"]',
      ) as HTMLButtonElement | null;
      expect(link).not.toBeNull();
      spyOn(component, 'openForecast');
      link!.click();
      expect(component.openForecast).toHaveBeenCalled();
    }));

    it('saveTimes wysyła start i program, a stan ikony się odświeża', fakeAsync(() => {
      fixture.detectChanges();
      tick();
      const ev = component.focusDay!.events[0];
      api.updateHouseholdEventTimes.and.returnValue(
        of({ ...ev, start_time: '10:00', duration_min: 135, planned_time: null }),
      );
      component.openTimes(ev);
      component.timeStart = '10:00';
      component.timeHours = '2';
      component.timeMinutes = '15';
      expect(component.timeEndPreview).toContain('koniec ok. 12:15');
      component.saveTimes();
      tick();
      expect(api.updateHouseholdEventTimes).toHaveBeenCalledWith(ev.id, {
        start_time: '10:00',
        duration_min: 135,
        planned_time: null,
      });
      expect(component.timeEvent).toBeNull();
      expect(component.events.find((e) => e.id === ev.id)?.start_time).toBe('10:00');
    }));

    it('koniec z zegara wylicza program (też przez północ)', () => {
      const pick = (v: string) => new CustomEvent('ionChange', { detail: { value: v } });
      component.timeStart = '13:32';
      component.onClockPicked('end', pick('15:39'));
      expect(component.programLabel).toBe('2 godz. 7 min');
      expect(component.timeEnd).toBe('15:39');
      component.timeStart = '23:30';
      component.onClockPicked('end', pick('00:20'));
      expect(component.programLabel).toBe('50 min');
      component.timeStart = '';
      component.onClockPicked('end', pick('10:00'));
      expect(component.timeError).toContain('początek');
    });

    it('program z koła ustawia czas bez końca (czajnik 3 min od 16:35)', () => {
      const pick = (v: string) => new CustomEvent('ionChange', { detail: { value: v } });
      component.timeStart = '16:35';
      component.onClockPicked('program', pick('00:03'));
      expect(component.programLabel).toBe('3 min');
      expect(component.timeEnd).toBe('16:38');
      component.onClockPicked('program', pick('00:00'));
      expect(component.timeError).toContain('co najmniej');
    });

    it('saveTimes zapisuje samą planowaną godzinę, gdy start jeszcze nie padł', fakeAsync(() => {
      fixture.detectChanges();
      tick();
      const ev = component.focusDay!.events[0];
      api.updateHouseholdEventTimes.and.returnValue(of({ ...ev, planned_time: '18:00' }));
      component.openTimes(ev);
      component.timePlanned = '18:00';
      component.saveTimes();
      tick();
      expect(api.updateHouseholdEventTimes).toHaveBeenCalledWith(ev.id, {
        start_time: null,
        duration_min: null,
        planned_time: '18:00',
      });
    }));

    it('saveTimes odrzuca złą godzinę i zły czas programu bez wołania API', fakeAsync(() => {
      fixture.detectChanges();
      tick();
      const ev = component.focusDay!.events[0];
      component.openTimes(ev);
      component.timeStart = '25:99';
      component.saveTimes();
      expect(component.timeError).toContain('Początek');
      component.timeStart = '10:00';
      component.timeMinutes = '75';
      component.saveTimes();
      expect(component.timeError).toContain('Czas programu');
      expect(api.updateHouseholdEventTimes).not.toHaveBeenCalled();
    }));
  });
});
