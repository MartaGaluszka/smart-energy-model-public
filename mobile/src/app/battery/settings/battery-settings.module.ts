import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { IonicModule } from '@ionic/angular';

import { BatterySettingsPageRoutingModule } from './battery-settings-routing.module';

import { BatterySettingsPage } from './battery-settings.page';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    IonicModule,
    BatterySettingsPageRoutingModule
  ],
  declarations: [BatterySettingsPage]
})
export class BatterySettingsPageModule {}
