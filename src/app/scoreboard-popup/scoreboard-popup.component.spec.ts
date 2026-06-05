import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ScoreboardPopupComponent } from './scoreboard-popup.component';

describe('ScoreboardPopupComponent', () => {
  let component: ScoreboardPopupComponent;
  let fixture: ComponentFixture<ScoreboardPopupComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ScoreboardPopupComponent]
    });
    fixture = TestBed.createComponent(ScoreboardPopupComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
