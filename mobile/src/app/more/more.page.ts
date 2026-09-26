import { Component } from '@angular/core';
import { addIcons } from 'ionicons';
import {
  batteryChargingOutline,
  calculatorOutline,
  cashOutline,
  flashOutline,
  partlySunnyOutline,
  receiptOutline,
  trendingUpOutline,
} from 'ionicons/icons';

@Component({
  selector: 'app-more',
  templateUrl: './more.page.html',
  styleUrls: ['./more.page.scss'],
  standalone: false,
})
export class MorePage {
  constructor() {
    addIcons({
      calculatorOutline,
      trendingUpOutline,
      batteryChargingOutline,
      flashOutline,
      partlySunnyOutline,
      cashOutline,
      receiptOutline,
    });
  }
}
