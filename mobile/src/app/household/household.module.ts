import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { HouseholdPageRoutingModule } from './household-routing.module';
import { HouseholdPage } from './household.page';

@NgModule({
  imports: [CommonModule, FormsModule, IonicModule, HouseholdPageRoutingModule],
  declarations: [HouseholdPage],
})
export class HouseholdPageModule {}
