import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { AlertController, ToastController } from '@ionic/angular';
import { of, throwError } from 'rxjs';
import { ApiService, HouseholdEventDto } from '../services/api.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { HouseholdPage } from './household.page';
import { dayAdvisorLine } from './household.types';

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
      'createHouseholdEvent',
      'deleteHouseholdEvent',
    ]);
    api.getHouseholdEvents.and.returnValue(of(sample));
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

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="rhythm-week"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="rhythm-hero"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="rhythm-axis"]')).toBeTruthy();
    expect(el.querySelectorAll('.se-rhythm-week__cell').length).toBe(7);
    expect(el.textContent).toContain('Rytm domu');
    expect(el.textContent).not.toContain('7 dni');
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
    expect(values.slice(0, 9)).toEqual([
      'sniadanie',
      'obiad',
      'kolacja',
      'zmywarka',
      'chleb',
      'grzejnik_lazienka',
      'podlogowka',
      'pranie',
      'suszarka',
    ]);
    expect(component.typeCatalog.find((t) => t.value === 'chleb')?.icon).toBe('se-bread');
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
