import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BatteryAnalyticsPage } from './battery-analytics.page';

describe('BatteryAnalyticsPage', () => {
  let component: BatteryAnalyticsPage;
  let fixture: ComponentFixture<BatteryAnalyticsPage>;

  beforeEach(() => {
    fixture = TestBed.createComponent(BatteryAnalyticsPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
