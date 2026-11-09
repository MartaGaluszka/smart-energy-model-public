import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { provideRouter } from '@angular/router';
import { BatterySchedulePage } from './battery-schedule.page';

describe('BatterySchedulePage', () => {
  let component: BatterySchedulePage;
  let fixture: ComponentFixture<BatterySchedulePage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [BatterySchedulePage],
      imports: [FormsModule],
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(BatterySchedulePage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
