import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import { BatterySettingsPage } from './battery-settings.page';

const routes: Routes = [
  {
    path: '',
    component: BatterySettingsPage
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class BatterySettingsPageRoutingModule {}
