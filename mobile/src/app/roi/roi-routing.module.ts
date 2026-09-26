import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { RoiPage } from './roi.page';

const routes: Routes = [
  {
    path: '',
    component: RoiPage,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class RoiPageRoutingModule {}
