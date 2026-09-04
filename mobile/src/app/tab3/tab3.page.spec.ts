import { ComponentFixture, TestBed } from '@angular/core/testing';
import { IonicModule } from '@ionic/angular';

import { ExploreContainerComponentModule } from '../explore-container/explore-container.module';

import {
  defaultRunLabelForHour,
  defaultRunLabelForViewedDay,
  isRunWindowScheduled,
  runWindowClockLabel,
  Tab3Page,
} from './tab3.page';

describe('run window schedule', () => {
  const today = '2026-09-04';
  const morning = new Date('2026-09-04T09:41:00');

  it('midday i peak są zaplanowane przed 12:00', () => {
    expect(isRunWindowScheduled('midday', { dayIso: today, now: morning, todayIso: today })).toBe(true);
    expect(isRunWindowScheduled('peak', { dayIso: today, now: morning, todayIso: today })).toBe(true);
    expect(isRunWindowScheduled('daily', { dayIso: today, now: morning, todayIso: today })).toBe(false);
  });

  it('od godziny granicy okno nie jest już zapowiedzią', () => {
    expect(isRunWindowScheduled('midday', {
      dayIso: today, now: new Date('2026-09-04T12:00:00'), todayIso: today,
    })).toBe(false);
    expect(isRunWindowScheduled('peak', {
      dayIso: today, now: new Date('2026-09-04T16:00:00'), todayIso: today,
    })).toBe(false);
  });

  it('dzień przeszły: brak danych to archiwum, nie zapowiedź', () => {
    expect(isRunWindowScheduled('peak', {
      dayIso: '2026-09-03', now: morning, todayIso: today,
    })).toBe(false);
  });

  it('dzień przyszły: wszystkie okna zaplanowane', () => {
    expect(isRunWindowScheduled('daily', {
      dayIso: '2026-09-05', now: morning, todayIso: today,
    })).toBe(true);
  });

  it('etykiety zegara', () => {
    expect(runWindowClockLabel('midday')).toBe('12:00');
    expect(runWindowClockLabel('peak')).toBe('16:00');
    expect(defaultRunLabelForHour(morning)).toBe('daily');
  });

  it('powrót na Dziś rano → Poranna, nie zostawia Popołudniowej', () => {
    expect(defaultRunLabelForViewedDay(today, { now: morning, todayIso: today })).toBe('daily');
  });

  it('jutro / pojutrze → Poranna; zamknięty dzień → Popołudniowa', () => {
    expect(defaultRunLabelForViewedDay('2026-09-05', { now: morning, todayIso: today })).toBe('daily');
    expect(defaultRunLabelForViewedDay('2026-09-06', { now: morning, todayIso: today })).toBe('daily');
    expect(defaultRunLabelForViewedDay('2026-09-03', { now: morning, todayIso: today })).toBe('peak');
  });

  it('dziś po 16:00 → Popołudniowa', () => {
    expect(defaultRunLabelForViewedDay(today, {
      now: new Date('2026-09-04T16:10:00'),
      todayIso: today,
    })).toBe('peak');
  });
});

describe('Tab3Page', () => {
  let component: Tab3Page;
  let fixture: ComponentFixture<Tab3Page>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [Tab3Page],
      imports: [IonicModule.forRoot(), ExploreContainerComponentModule]
    }).compileComponents();

    fixture = TestBed.createComponent(Tab3Page);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
