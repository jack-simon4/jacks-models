import { NgModule, Injectable } from '@angular/core';
import { ServerModule } from '@angular/platform-server';
import {
  HTTP_INTERCEPTORS, HttpRequest, HttpHandler,
  HttpInterceptor, HttpResponse, HttpEvent,
} from '@angular/common/http';
import { Observable, of } from 'rxjs';
import * as fs from 'fs';
import * as path from 'path';

import { AppModule } from './app.module';
import { AppComponent } from './app.component';

/**
 * During prerender Angular runs in Node.js with no server.
 * Relative HttpClient requests to /assets/* would normally fail because there
 * is no base URL. This interceptor catches those requests and reads the file
 * directly from the dist output on disk so the prerendered HTML contains
 * real data instead of empty loading states.
 */
@Injectable()
export class AssetInterceptor implements HttpInterceptor {
  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    const url = req.url.replace(/^\//, '');
    if (url.startsWith('assets/')) {
      try {
        const filePath = path.join(process.cwd(), 'dist', 'scoreboard-app', 'browser', url);
        const raw  = fs.readFileSync(filePath, 'utf8');
        const body = url.endsWith('.json') ? JSON.parse(raw) : raw;
        return of(new HttpResponse({ body, status: 200 }));
      } catch {
        // file not found — fall through to normal handler
      }
    }
    return next.handle(req);
  }
}

@NgModule({
  imports: [AppModule, ServerModule],
  providers: [
    { provide: HTTP_INTERCEPTORS, useClass: AssetInterceptor, multi: true },
  ],
  bootstrap: [AppComponent],
})
export class AppServerModule {}
