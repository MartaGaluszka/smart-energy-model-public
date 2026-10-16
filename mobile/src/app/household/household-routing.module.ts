import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { HouseholdPage } from './household.page';

const routes: Routes = [
  {
    path: '',
    component: HouseholdPage,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class HouseholdPageRoutingModule {}
