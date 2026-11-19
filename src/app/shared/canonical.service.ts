import { Injectable, Inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class CanonicalService {
  constructor(@Inject(DOCUMENT) private doc: Document) {}

  set(url: string) {
    let el: HTMLLinkElement | null = this.doc.querySelector('link[rel="canonical"]');
    if (!el) {
      el = this.doc.createElement('link');
      el.setAttribute('rel', 'canonical');
      this.doc.head.appendChild(el);
    }
    el.setAttribute('href', url);
  }
}
