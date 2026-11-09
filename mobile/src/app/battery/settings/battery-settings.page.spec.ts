import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { provideRouter } from '@angular/router';
import { BatterySettingsPage } from './battery-settings.page';

describe('BatterySettingsPage', () => {
  let component: BatterySettingsPage;
  let fixture: ComponentFixture<BatterySettingsPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [BatterySettingsPage],
      imports: [FormsModule],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(BatterySettingsPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
