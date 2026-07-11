import { Injectable, Inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class JsonLdService {
  private scripts = new Map<string, HTMLScriptElement>();

  constructor(@Inject(DOCUMENT) private doc: Document) {}

  set(id: string, schema: object) {
    let el = this.scripts.get(id);
    if (!el) {
      el = this.doc.createElement('script');
      el.type = 'application/ld+json';
      el.id = `ld-${id}`;
      this.doc.head.appendChild(el);
      this.scripts.set(id, el);
    }
    el.text = JSON.stringify(schema);
  }

  remove(id: string) {
    const el = this.scripts.get(id);
    if (el) {
      el.remove();
      this.scripts.delete(id);
    }
  }
}
