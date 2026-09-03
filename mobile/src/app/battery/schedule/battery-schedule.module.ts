import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { IonicModule } from '@ionic/angular';

import { BatterySchedulePageRoutingModule } from './battery-schedule-routing.module';

import { BatterySchedulePage } from './battery-schedule.page';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    IonicModule,
    BatterySchedulePageRoutingModule
  ],
  declarations: [BatterySchedulePage]
})
export class BatterySchedulePageModule {}
