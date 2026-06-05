import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SoccerScoreboardComponent } from './soccer-scoreboard.component';

describe('SoccerScoreboardComponent', () => {
  let component: SoccerScoreboardComponent;
  let fixture: ComponentFixture<SoccerScoreboardComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [SoccerScoreboardComponent]
    });
    fixture = TestBed.createComponent(SoccerScoreboardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
