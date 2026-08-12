import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { SimulatorPageRoutingModule } from './simulator-routing.module';
import { SimulatorPage } from './simulator.page';

@NgModule({
  imports: [CommonModule, FormsModule, IonicModule, SimulatorPageRoutingModule],
  declarations: [SimulatorPage],
})
export class SimulatorPageModule {}
