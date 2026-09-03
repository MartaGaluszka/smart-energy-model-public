import { Component, OnInit } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { Observable } from 'rxjs';
import { HomeDataService, SyncStatus } from '../services/home-data.service';

@Component({
  selector: 'app-tab2',
  templateUrl: 'tab2.page.html',
  styleUrls: ['tab2.page.scss'],
  standalone: false,
})
export class Tab2Page implements OnInit, ViewWillEnter {
  sync$!: Observable<SyncStatus>;

  constructor(readonly homeData: HomeDataService) {}

  ngOnInit() {
    this.sync$ = this.homeData.getSyncStatus();
  }

  ionViewWillEnter() {
    this.homeData.refreshAll();
  }

  onSync() {
    this.homeData.triggerSync().subscribe();
  }

  minutesAgo(date: Date | null): string {
    if (!date) return 'nigdy';
    const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
    if (minutes < 1) return 'przed chwilą';
    if (minutes === 1) return '1 minutę temu';
    return `${minutes} min temu`;
  }
}
