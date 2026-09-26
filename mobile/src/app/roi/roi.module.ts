import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { RoiPageRoutingModule } from './roi-routing.module';
import { RoiPage } from './roi.page';

@NgModule({
  imports: [CommonModule, FormsModule, IonicModule, RoiPageRoutingModule],
  declarations: [RoiPage],
})
export class RoiPageModule {}
