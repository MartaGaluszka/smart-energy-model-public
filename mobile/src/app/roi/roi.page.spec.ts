import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ApiService, RoiAssumptions, RoiCalculateResponse } from '../services/api.service';
import { RoiPage } from './roi.page';

describe('RoiPage Parametry', () => {
  let fixture: ComponentFixture<RoiPage>;
  let component: RoiPage;
  let api: jasmine.SpyObj<ApiService>;

  const assumptions: RoiAssumptions = {
    capex_pln: 40800,
    battery_capex_pln: 0,
    opex_pln_year: 120,
    inflation_pct: 0,
    seller_baseline_pln_year: null,
  };

  beforeEach(async () => {
    api = jasmine.createSpyObj('ApiService', [
      'getRoiAssumptions',
      'putRoiAssumptions',
      'calculateRoi',
    ]);
    api.getRoiAssumptions.and.returnValue(of(assumptions));
    api.putRoiAssumptions.and.returnValue(of(assumptions));

    await TestBed.configureTestingModule({
      declarations: [RoiPage],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [{ provide: ApiService, useValue: api }],
    }).compileComponents();

    fixture = TestBed.createComponent(RoiPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create with default period and opex before/after assumptions', fakeAsync(() => {
    tick();
    fixture.detectChanges();

    expect(component.opex).toBe(120);
    expect(component.periodStart).toBe('2025-06-01');
    expect(component.periodEnd).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(component.periodStart <= component.periodEnd).toBe(true);
  }));

  it('shows Przegląd [zł/rok], Od and Do with visible values in Parametry', fakeAsync(() => {
    tick();
    component.loading = false;
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Przegląd [zł/rok]');
    expect(text).toContain('Parametry');
    const startBtn: HTMLButtonElement = fixture.nativeElement.querySelector('[data-testid="roi-period-start"]');
    const endBtn: HTMLButtonElement = fixture.nativeElement.querySelector('[data-testid="roi-period-end"]');
    expect(startBtn).toBeTruthy();
    expect(endBtn).toBeTruthy();
    expect(startBtn.textContent?.trim()).toBe(component.periodStart);
    expect(endBtn.textContent?.trim()).toBe(component.periodEnd);

    const opexInput: HTMLInputElement = fixture.nativeElement.querySelector('[data-testid="roi-opex"]');
    expect(opexInput).toBeTruthy();
    expect(Number(opexInput.value)).toBe(120);
  }));

  it('applies opex from API assumptions even for known CAPEX presets', fakeAsync(() => {
    api.getRoiAssumptions.and.returnValue(of({
      ...assumptions,
      opex_pln_year: 150,
    }));
    const next = TestBed.createComponent(RoiPage);
    next.detectChanges();
    tick();
    expect(next.componentInstance.opex).toBe(150);
  }));

  it('updates Od/Do labels when period changes', fakeAsync(() => {
    tick();
    component.loading = false;
    component.onPeriodStart('2025-01-15');
    expect(component.periodStart).toBe('2025-06-01');
    component.onPeriodStart('2025-06-15');
    component.onPeriodEnd('2025-12-31');
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[data-testid="roi-period-start"]').textContent.trim())
      .toBe('2025-06-15');
    expect(fixture.nativeElement.querySelector('[data-testid="roi-period-end"]').textContent.trim())
      .toBe('2025-12-31');
  }));

  it('does not move Do past today and clears the result when Od changes', fakeAsync(() => {
    tick();
    component.result = { opex_pln_period: 120 } as RoiCalculateResponse;
    component.onPeriodEnd('2099-01-01');
    expect(component.periodEnd).toBe(component.today);
    expect(component.result).toEqual(jasmine.objectContaining({ opex_pln_period: 120 }));

    component.onPeriodStart('2025-06-15');
    expect(component.periodStart).toBe('2025-06-15');
    expect(component.result).toBeNull();
  }));

  it('opens the calendar from Od and Do after the parameters have loaded', fakeAsync(() => {
    tick();
    component.loading = false;
    fixture.detectChanges();

    const opened: string[] = [];
    spyOn(component, 'openDate').and.callFake(() => opened.push('tap'));
    const start: HTMLButtonElement = fixture.nativeElement.querySelector('[data-testid="roi-period-start"]');
    const end: HTMLButtonElement = fixture.nativeElement.querySelector('[data-testid="roi-period-end"]');
    start.click();
    end.click();
    expect(opened).toEqual(['tap', 'tap']);
  }));

  it('openDate presents the modal and ignores a missing one', () => {
    const present = jasmine.createSpy('present');
    component.openDate({ present });
    expect(present).toHaveBeenCalledTimes(1);
    expect(() => component.openDate(undefined)).not.toThrow();
    expect(() => component.openDate({})).not.toThrow();
  });

  it('calculate sends the yearly review and keeps the bill savings from the API', fakeAsync(() => {
    tick();
    const payload: RoiCalculateResponse = {
      period_start: '2025-06-01',
      period_end: component.periodEnd,
      savings_pln_period: 3641.9,
      deposit_pln_period: 1243.32,
      opex_pln_period: 120,
      cash_gain_pln_period: 4765.22,
      recovered_pln: 4765.22,
      remaining_pln: 0,
      remaining_years: 0,
      savings_pln_year_annualized: 3000,
      roi_percent: 10,
      payback_years: 1,
      payback_reached_in_period: true,
    };
    api.calculateRoi.and.returnValue(of(payload));
    component.opex = 120;
    component.calculate();
    tick();

    const sent = api.putRoiAssumptions.calls.mostRecent().args[0] as RoiAssumptions;
    expect(sent.opex_pln_year).toBe(120);
    expect(api.calculateRoi).toHaveBeenCalledWith('2025-06-01', component.periodEnd);
    expect(component.result?.savings_pln_period).toBe(3641.9);
    expect(component.result?.opex_pln_period).toBe(120);
    expect(component.calculating).toBeFalse();
    expect(component.error).toBeNull();
  }));

  it('calculate shows the API message and a fallback when the detail is not text', fakeAsync(() => {
    tick();
    api.putRoiAssumptions.and.returnValue(throwError(() => ({ error: { detail: 'brak danych' } })));
    component.calculate();
    tick();
    expect(component.calculating).toBeFalse();
    expect(component.error).toBe('brak danych');
    expect(component.result).toBeNull();

    api.putRoiAssumptions.and.returnValue(throwError(() => ({ error: { detail: { code: 'X' } } })));
    component.calculate();
    tick();
    expect(component.error).toContain('Nie udało się policzyć zwrotu');
  }));
});
