// Tiny observable store for the game page (user + skin catalogue).
import { session } from './api.js';

const listeners = new Set();

export const store = {
  user: session.user,
  skins: [],

  setUser(user) {
    this.user = user;
    session.save(null, user);
    this.emit();
  },
  setSkins(skins) {
    this.skins = skins;
    this.emit();
  },
  skinBySlug(slug) {
    return this.skins.find((s) => s.slug === slug) || null;
  },
  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  emit() {
    listeners.forEach((fn) => fn(this));
  },
};

