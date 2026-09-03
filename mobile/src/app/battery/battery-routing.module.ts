import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { BatteryPage } from './battery.page';
import { UnsavedChangesGuard } from '../guards/unsaved-changes.guard';

const routes: Routes = [
  {
    path: '',
    component: BatteryPage,
    canDeactivate: [UnsavedChangesGuard],
    children: [
      {
        path: 'settings',
        loadChildren: () =>
          import('./settings/battery-settings.module').then((m) => m.BatterySettingsPageModule),
      },
      {
        path: 'schedule',
        loadChildren: () =>
          import('./schedule/battery-schedule.module').then((m) => m.BatterySchedulePageModule),
      },
      {
        path: 'analytics',
        loadChildren: () =>
          import('./analytics/battery-analytics.module').then((m) => m.BatteryAnalyticsPageModule),
      },
      {
        path: '',
        redirectTo: 'settings',
        pathMatch: 'full',
      },
    ],
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class BatteryPageRoutingModule {}
