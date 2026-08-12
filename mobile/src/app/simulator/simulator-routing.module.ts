import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { SimulatorPage } from './simulator.page';

const routes: Routes = [
  {
    path: '',
    component: SimulatorPage,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class SimulatorPageRoutingModule {}
