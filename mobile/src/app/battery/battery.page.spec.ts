import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { of, Subject } from 'rxjs';
import { BatteryPage, BatteryTab } from './battery.page';
import { BatteryStateService } from './services/battery-state.service';

describe('BatteryPage tabs', () => {
  let fixture: ComponentFixture<BatteryPage>;
  let component: BatteryPage;
  let navigateSpy: jasmine.Spy;
  let routerEvents$: Subject<unknown>;

  beforeEach(async () => {
    routerEvents$ = new Subject();
    navigateSpy = jasmine.createSpy('navigate').and.returnValue(Promise.resolve(true));

    await TestBed.configureTestingModule({
      declarations: [BatteryPage],
      imports: [CommonModule],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [
        {
          provide: Router,
          useValue: {
            url: '/tabs/battery/settings',
            events: routerEvents$.asObservable(),
            navigate: navigateSpy,
          },
        },
        {
          provide: BatteryStateService,
          useValue: {
            loading: () => false,
            saving: () => false,
            hasUnsavedChanges: () => false,
            loadSettings: jasmine.createSpy('loadSettings'),
            saveSettings: () => of(void 0),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(BatteryPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('renders three tab buttons (Ustawienia / Harmonogram / Analityka)', () => {
    const buttons = fixture.nativeElement.querySelectorAll('.se-battery-tab');
    expect(buttons.length).toBe(3);
    const labels = Array.from(buttons as NodeListOf<HTMLButtonElement>).map((b) => b.textContent?.trim());
    expect(labels).toEqual(['Ustawienia', 'Harmonogram', 'Analityka']);
  });

  it('marks settings as active by default', () => {
    const active = fixture.nativeElement.querySelector('.se-battery-tab--active');
    expect(active?.getAttribute('data-tab')).toBe('settings');
    expect(active?.getAttribute('aria-selected')).toBe('true');
  });

  it('selectTab navigates to the chosen battery child route', () => {
    component.selectTab('schedule');
    expect(component.activeTab).toBe('schedule' as BatteryTab);
    expect(navigateSpy).toHaveBeenCalledWith(['/tabs/battery', 'schedule']);
  });

  it('clicking Analityka activates that tab and navigates', () => {
    const analyticsBtn: HTMLButtonElement = fixture.nativeElement.querySelector('[data-tab="analytics"]');
    analyticsBtn.click();
    fixture.detectChanges();

    expect(component.activeTab).toBe('analytics');
    expect(navigateSpy).toHaveBeenCalledWith(['/tabs/battery', 'analytics']);
    expect(fixture.nativeElement.querySelector('.se-battery-tab--active')?.getAttribute('data-tab'))
      .toBe('analytics');
  });

  it('keeps all three tabs in the DOM after switching (no ion-segment collapse)', () => {
    component.selectTab('analytics');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.se-battery-tab').length).toBe(3);
  });
});
