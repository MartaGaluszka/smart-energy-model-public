import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import { BatteryAnalyticsPage } from './battery-analytics.page';

const routes: Routes = [
  {
    path: '',
    component: BatteryAnalyticsPage
  }
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class BatteryAnalyticsPageRoutingModule {}
