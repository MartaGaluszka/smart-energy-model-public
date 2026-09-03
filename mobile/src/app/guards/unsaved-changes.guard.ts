import { Injectable, inject } from '@angular/core';
import { CanDeactivate } from '@angular/router';
import { AlertController } from '@ionic/angular';
import { BatteryStateService } from '../battery/services/battery-state.service';

export interface ComponentCanDeactivate {
  canDeactivate: () => boolean | Promise<boolean>;
}

@Injectable({
  providedIn: 'root'
})
export class UnsavedChangesGuard implements CanDeactivate<unknown> {
  private alertController = inject(AlertController);
  private stateService = inject(BatteryStateService);

  async canDeactivate(): Promise<boolean> {
    // If no unsaved changes, allow navigation
    if (!this.stateService.hasUnsavedChanges()) {
      return true;
    }

    // Show Ionic alert dialog
    const alert = await this.alertController.create({
      header: 'Niezapisane zmiany',
      message: 'Masz niezapisane zmiany w ustawieniach baterii. Czy na pewno chcesz opuścić tę stronę? Zmiany zostaną utracone.',
      buttons: [
        {
          text: 'Anuluj',
          role: 'cancel',
          cssClass: 'secondary',
          handler: () => {
            return false;
          }
        },
        {
          text: 'Opuść',
          role: 'destructive',
          cssClass: 'danger',
          handler: () => {
            // Optionally: reset draft state
            // this.stateService.discardChanges();
            return true;
          }
        }
      ]
    });

    await alert.present();
    const { role } = await alert.onDidDismiss();
    
    // Return false if user cancelled, true if they chose to leave
    return role !== 'cancel';
  }
}
