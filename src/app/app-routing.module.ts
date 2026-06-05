import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { SoccerScoreboardComponent } from './soccer-scoreboard/soccer-scoreboard.component';
import { ScoreboardComponent } from './scoreboard/scoreboard.component';
import { AboutComponent } from './about/about.component';
import { ResultsComponent } from './results/results.component';

import { SoccerSeoPageComponent } from './seo-pages/soccer-seo-page.component';
import { CollegeBaseballSeoPageComponent } from './seo-pages/college-baseball-seo-page.component';
import { NhlSeoPageComponent } from './seo-pages/nhl-seo-page.component';
import { NcaamSeoPageComponent } from './seo-pages/ncaam-seo-page.component';
import { NbaSeoPageComponent } from './seo-pages/nba-seo-page.component';
import { NcaafSeoPageComponent } from './seo-pages/ncaaf-seo-page.component';
import { MlbSeoPageComponent } from './seo-pages/mlb-seo-page.component';
import { MlbPropsComponent } from './mlb-props/mlb-props.component';
import { NflSeoPageComponent } from './seo-pages/nfl-seo-page.component';

const routes: Routes = [
  { path: '', component: HomeComponent },
{ path: 'scoreboard', component: ScoreboardComponent },
  { path: 'about', component: AboutComponent },
  { path: 'results', component: ResultsComponent },
  { path: 'soccer-scoreboard', component: SoccerScoreboardComponent },
  { path: 'mlb-props', component: MlbPropsComponent },

  // SEO Landing Pages
  { path: 'nfl-predictions', component: NflSeoPageComponent },
  { path: 'mlb-predictions', component: MlbSeoPageComponent },
  { path: 'ncaaf-predictions', component: NcaafSeoPageComponent },
  { path: 'nba-predictions', component: NbaSeoPageComponent },
  { path: 'ncaam-predictions', component: NcaamSeoPageComponent },
  { path: 'nhl-predictions', component: NhlSeoPageComponent },
  { path: 'college-baseball-predictions', component: CollegeBaseballSeoPageComponent },
  { path: 'soccer-predictions', component: SoccerSeoPageComponent },
];

@NgModule({
  imports: [
    RouterModule.forRoot(routes, {
    initialNavigation: 'enabledBlocking' // recommended for SEO + prerender
})
  ],
  exports: [RouterModule]
})
export class AppRoutingModule { }
