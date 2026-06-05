import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';

@Component({
  selector: 'app-scoreboard-popup',
  templateUrl: 'scoreboard-popup.component.html',
})
export class ScoreboardPopupComponent {
  constructor(
    public dialogRef: MatDialogRef<ScoreboardPopupComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any
  ) {}

  getNcaamSpread(): string {
    if (this.data && this.data.selectedSport === 'NCAAM' && this.data.ncaamSpreads) {
      const homeTeam = this.data.selectedHomeTeam.trim();
      return this.data.ncaamSpreads[homeTeam] || '';
    }
    return '';
  }
  getNBASpread(): string {
    if (this.data && this.data.selectedSport === 'NBA' && this.data.NBASpreads) {
      const homeTeam = this.data.selectedHomeTeam.trim();
      return this.data.NBASpreads[homeTeam] || '';
    }
    return '';
  }

  getNFLSpread(): string {
    if (this.data && this.data.selectedSport === 'NFL' && this.data.NFLSpreads) {
      const homeTeam = this.data.selectedHomeTeam.trim();
      return this.data.NFLSpreads[homeTeam] || '';
    }
    return '';
  }

  onSave(): void {
    // Add your save logic here
    // For example, you can send the data to a service or perform any other save operation
    console.log('Save button clicked!');
  }


}

