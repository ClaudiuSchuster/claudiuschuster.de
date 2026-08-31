# claudiuschuster.de

[![Verify](https://github.com/ClaudiuSchuster/claudiuschuster.de/actions/workflows/verify.yml/badge.svg)](https://github.com/ClaudiuSchuster/claudiuschuster.de/actions/workflows/verify.yml)

[![Claudiu Schuster — Feel the data flow ...](assets/social-preview.png)](https://claudiuschuster.de/)

The source of [claudiuschuster.de](https://claudiuschuster.de/) — a bilingual personal website and an executable portfolio of design, frontend and operational craft.

The site is deliberately dependency-free. It ships semantic HTML, hand-written CSS and small progressive JavaScript enhancements without tracking, cookies, remote scripts or a client-side framework.

## Two design worlds, one content model

- **Data Flow Atelier** is warm, atmospheric and technically precise. It is the first-visit default.
- **Prismatic Workshop** is bold, modular and playfully engineered.
- A persistent, accessible design switch changes the visual system without leaving the page.
- German and English share the same structure and behavior.
- Core content remains available without JavaScript and respects reduced-motion preferences.

The two theme stylesheets under [`concepts/`](concepts/) power both design directions. The root pages combine them into the production experience.

## Engineering highlights

- deterministic, dependency-free build written in Python
- content-derived SHA-256 fingerprints for every production asset
- immutable long-term caching for fingerprinted assets and no-store HTML
- strict Content Security Policy and defensive browser headers
- local-only scripts, styles and images; no runtime third-party requests
- structural checks for semantics, accessibility basics, local references and social metadata
- pinned GitHub Actions dependencies with read-only workflow permissions

## Local preview

```bash
make serve
```

Open <http://127.0.0.1:4180/>.

## Verification and production build

```bash
make check
make build
```

`make check` validates the source. `make build` runs those checks and creates the deployable `dist/` bundle. Preview that exact production output with:

```bash
make serve-dist
```

The build fingerprints CSS, JavaScript and images. HTML is never cached; fingerprinted assets may safely be cached as immutable for one year without mixing a new document with stale styles.

The Open Graph and Twitter metadata reference a dedicated 1200×630 social card for rich link previews.

## Production safety

Only the generated `dist/` bundle is deployed. DNS, mail routing, certificates and `.well-known` content remain outside the replacement scope.

Security reports should follow the private process in [SECURITY.md](SECURITY.md). Contributions are described in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The code is available under the [MIT License](LICENSE).
