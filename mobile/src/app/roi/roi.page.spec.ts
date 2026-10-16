import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of } from 'rxjs';
import { ApiService, RoiAssumptions } from '../services/api.service';
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
    expect(component.periodStart).toMatch(/^\d{4}-\d{2}-\d{2}$/);
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
    component.onPeriodEnd('2025-12-31');
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[data-testid="roi-period-start"]').textContent.trim())
      .toBe('2025-01-15');
    expect(fixture.nativeElement.querySelector('[data-testid="roi-period-end"]').textContent.trim())
      .toBe('2025-12-31');
  }));
});
