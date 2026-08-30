# claudiuschuster.de

Personal website of Claudiu Schuster.

The first iteration is a dependency-free static website with two visual worlds:

- **Data Flow Atelier** — warm, atmospheric and technically precise.
- **Prismatic Workshop** — bold, modular and playfully engineered.

Data Flow Atelier is the first-visit default. A persistent, accessible design switch activates Prismatic Workshop without leaving the page. Core content remains available without JavaScript; the switch is a progressive enhancement. Both languages respect reduced-motion preferences and link only to intentionally public GitHub resources.

## Local preview

```bash
make serve
```

Open <http://127.0.0.1:4180/>.

## Checks

```bash
make build
```

This validates the source and creates the deployable `dist/` bundle. Every CSS, JavaScript and social-preview asset receives a content-derived SHA-256 fingerprint in its filename. HTML is never cached; fingerprinted assets may safely be cached as immutable for one year without mixing a new document with stale styles.

Preview the exact production bundle with:

```bash
make serve-dist
```

The root page and `/en.html` are the combined production candidates. The individual concept pages remain available as design references during review. The Open Graph and Twitter metadata reference a dedicated 1200×630 social card for Telegram and other link previews.

## Production safety

Production deployment uses only the generated `dist/` bundle. DNS, mail routing, certificates and `.well-known` content remain outside the replacement scope.
