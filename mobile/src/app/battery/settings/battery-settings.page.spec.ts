import { ComponentFixture, TestBed } from '@angular/core/testing';
import { BatterySettingsPage } from './battery-settings.page';

describe('BatterySettingsPage', () => {
  let component: BatterySettingsPage;
  let fixture: ComponentFixture<BatterySettingsPage>;

  beforeEach(() => {
    fixture = TestBed.createComponent(BatterySettingsPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
