import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of } from 'rxjs';
import { ApiService } from '../services/api.service';
import { BatteryStateService } from '../battery/services/battery-state.service';
import { HomeDataService } from '../services/home-data.service';
import { shiftIsoDate, todayIsoLocal } from '../utils/date-utils';
import { Tab1Page } from './tab1.page';

describe('Tab1Page household calendar', () => {
  let fixture: ComponentFixture<Tab1Page>;
  let component: Tab1Page;
  let api: jasmine.SpyObj<ApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj('ApiService', [
      'getHouseholdEvents',
      'getShadowSavings',
      'getAcRuntime',
      'getBatteryPlan',
      'getForecastHourly',
      'postAcRuntime',
    ]);
    api.getHouseholdEvents.and.returnValue(
      of([
        {
          id: 1,
          event_date: todayIsoLocal(),
          event_type: 'pranie',
          impact: 'up',
          note: null,
        },
      ]),
    );
    api.getShadowSavings.and.returnValue(
      of({
        period_from: '',
        period_to: '',
        shadow_savings_pln: 0,
        baseline_cost_pln: 0,
        actual_cost_pln: 0,
        method_note: '',
        is_hypothetical: true,
      }),
    );
    api.getAcRuntime.and.returnValue(
      of({
        hours_safe: 0,
        suggested_off_at: null,
        night_load_kw: 0,
        night_house_kwh: 0,
        hours_until_morning: 0,
        battery_covers_from: '',
        ac_power_kw: 1.2,
        show_card: false,
        ac_day: false,
        soc_now_percent: null,
        soc_min_morning_percent: 10,
        battery_capacity_kwh: 10,
        efficiency_pct: 90,
        note: '',
      }),
    );
    api.getBatteryPlan.and.returnValue(
      of({ date: todayIsoLocal(), season: 'autumn', hours: [], note: '' }),
    );
    api.getForecastHourly.and.returnValue(
      of({ day: todayIsoLocal(), hours: [], total_kwh: 0, model_path: '' }),
    );

    await TestBed.configureTestingModule({
      declarations: [Tab1Page],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [
        { provide: ApiService, useValue: api },
        {
          provide: HomeDataService,
          useValue: {
            getKpi: () => of(null),
            getSyncStatus: () =>
              of({ offline: false, syncing: false, lastSyncedAt: null, message: null, messageKind: null, dataDay: null }),
            getBatterySuggestion: () => of(null),
            getSuggestions: () => of([]),
            refreshAll: () => undefined,
            triggerSync: () => of(null),
          },
        },
        {
          provide: BatteryStateService,
          useValue: {
            loadSettings: jasmine.createSpy('loadSettings'),
            persistAcPowerKw: () => of(void 0),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Tab1Page);
    component = fixture.componentInstance;
  });

  it('loads teaser (3 days) and week strip (7 days)', fakeAsync(() => {
    fixture.detectChanges();
    tick();
    fixture.detectChanges();

    expect(api.getHouseholdEvents).toHaveBeenCalled();
    const [from, to] = api.getHouseholdEvents.calls.mostRecent().args;
    expect(from).toBe(todayIsoLocal());
    expect(to).toBe(shiftIsoDate(todayIsoLocal(), 6));
    expect(component.calendarTeaser.length).toBe(3);
    expect(component.calendarWeek.length).toBe(7);
    expect(component.calendarTeaser[0].count).toBe(1);
    expect(component.calendarTeaser[0].labels[0]).toContain('Pranie');

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="home-cal-teaser"]')).toBeTruthy();
    expect(el.querySelector('[data-testid="home-cal-week"]')).toBeTruthy();
    expect(el.querySelectorAll('.se-cal-week__cell').length).toBe(7);
  }));
});
