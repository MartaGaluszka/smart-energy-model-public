import { ComponentFixture, TestBed } from '@angular/core/testing';
import { IonicModule } from '@ionic/angular';
import { of } from 'rxjs';

import { HomeDataService, SyncStatus } from '../services/home-data.service';
import { Tab2Page } from './tab2.page';

describe('Tab2Page', () => {
  let component: Tab2Page;
  let fixture: ComponentFixture<Tab2Page>;

  const idle: SyncStatus = {
    lastSyncedAt: null,
    syncing: false,
    offline: false,
    dataDay: null,
    message: null,
    messageKind: null,
    rateLimited: false,
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [Tab2Page],
      imports: [IonicModule.forRoot()],
      providers: [
        {
          provide: HomeDataService,
          useValue: {
            getSyncStatus: () => of(idle),
            triggerSync: () => of(idle),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Tab2Page);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
