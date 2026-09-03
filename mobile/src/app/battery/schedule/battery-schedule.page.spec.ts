import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BatterySchedulePage } from './battery-schedule.page';

describe('BatterySchedulePage', () => {
  let component: BatterySchedulePage;
  let fixture: ComponentFixture<BatterySchedulePage>;

  beforeEach(() => {
    fixture = TestBed.createComponent(BatterySchedulePage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
