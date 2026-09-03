import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { IonicModule } from '@ionic/angular';

import { BatteryAnalyticsPageRoutingModule } from './battery-analytics-routing.module';

import { BatteryAnalyticsPage } from './battery-analytics.page';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    IonicModule,
    BatteryAnalyticsPageRoutingModule
  ],
  declarations: [BatteryAnalyticsPage]
})
export class BatteryAnalyticsPageModule {}
