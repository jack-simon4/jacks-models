import { BrowserModule } from '@angular/platform-browser';
import { RouterModule } from '@angular/router';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { AppComponent } from './app.component';
import { RibbonComponent } from './ribbon/ribbon.component'; // Make sure it's imported here
import { ScoreboardComponent } from './scoreboard/scoreboard.component';
import { TeamsComponent } from './teams/teams.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { ScoreboardPopupComponent } from './scoreboard-popup/scoreboard-popup.component';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { AboutComponent } from './about/about.component';
import { AppRoutingModule } from './app-routing.module';
import { ResultsComponent } from './results/results.component';
import { SoccerScoreboardComponent } from './soccer-scoreboard/soccer-scoreboard.component';
import { AngularFireModule } from '@angular/fire/compat';
import { AngularFirestoreModule } from '@angular/fire/compat/firestore';
import { environment } from '../environments/environment';
import { CommonModule } from '@angular/common';
import { NflSeoPageComponent } from './seo-pages/nfl-seo-page.component';
import { MlbSeoPageComponent } from './seo-pages/mlb-seo-page.component';
import { NcaafSeoPageComponent } from './seo-pages/ncaaf-seo-page.component';
import { NbaSeoPageComponent } from './seo-pages/nba-seo-page.component';
import { NcaamSeoPageComponent } from './seo-pages/ncaam-seo-page.component';
import { NhlSeoPageComponent } from './seo-pages/nhl-seo-page.component';
import { CollegeBaseballSeoPageComponent } from './seo-pages/college-baseball-seo-page.component';
import { SoccerSeoPageComponent } from './seo-pages/soccer-seo-page.component';
import { WorldCupSeoPageComponent } from './seo-pages/world-cup-seo-page.component';
import { HomeComponent } from './home/home.component';
import { MlbPropsComponent } from './mlb-props/mlb-props.component';





@NgModule({
  declarations: [
    AppComponent,
    RibbonComponent,
    ScoreboardComponent,
    TeamsComponent,
    ScoreboardPopupComponent,
    AboutComponent,
    ResultsComponent,
    SoccerScoreboardComponent, 
    NflSeoPageComponent,
    MlbSeoPageComponent,
    NcaafSeoPageComponent,
    NbaSeoPageComponent,
    NcaamSeoPageComponent,
    NhlSeoPageComponent,
    CollegeBaseballSeoPageComponent,
    SoccerSeoPageComponent,
    WorldCupSeoPageComponent,
      HomeComponent,
    MlbPropsComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    BrowserAnimationsModule,
    MatDialogModule,
    MatInputModule,
    MatSelectModule,
    AppRoutingModule, // Ensure this is here
    MatAutocompleteModule,
    AngularFireModule.initializeApp(environment.firebaseConfig),
    AngularFirestoreModule,
    CommonModule,
  ],
  providers: [],
  bootstrap: [AppComponent],
})
export class AppModule { }


