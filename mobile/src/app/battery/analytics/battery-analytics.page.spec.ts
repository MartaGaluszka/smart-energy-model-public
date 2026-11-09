import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { provideRouter } from '@angular/router';
import { BatteryAnalyticsPage } from './battery-analytics.page';

describe('BatteryAnalyticsPage', () => {
  let component: BatteryAnalyticsPage;
  let fixture: ComponentFixture<BatteryAnalyticsPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [BatteryAnalyticsPage],
      imports: [FormsModule],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(BatteryAnalyticsPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
