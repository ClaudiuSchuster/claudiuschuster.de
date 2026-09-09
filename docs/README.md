# Development documentation

This is the technical entry point for the `claudiuschuster.de` repository.
The root [README](../README.md) is intentionally kept as a concise showcase;
development, verification, hosting and publication details live here.

## About the site

The repository is the source of [claudiuschuster.de](https://claudiuschuster.de/),
a bilingual personal website and an executable portfolio of design, frontend
and operational craft.

The site is deliberately dependency-free. It ships semantic HTML, hand-written
CSS and small progressive JavaScript enhancements without tracking, cookies,
remote scripts or a client-side framework.

## Design and content model

- **Data Flow Atelier** is warm, atmospheric and technically precise. It is the first-visit default.
- **Prismatic Workshop** is bold, modular and playfully engineered.
- A persistent, accessible design switch changes the visual system without leaving the page.
- German and English share the same structure and behavior.
- Core content remains available without JavaScript and respects reduced-motion preferences.

The two theme stylesheets under [`../assets/`](../assets/) power both design
directions. The root pages combine them into the production experience. The
social-preview source and renderer live under [`../assets/scripts/`](../assets/scripts/);
regenerate the PNG with `make render-social-preview`.

## Engineering highlights

- deterministic, dependency-free build written in Python
- content-derived SHA-256 fingerprints for every production asset
- immutable long-term caching for fingerprinted assets and no-store HTML
- strict Content Security Policy and defensive browser headers
- local-only scripts, styles and images; no runtime third-party requests
- structural checks for semantics, accessibility basics, local references and social metadata
- pinned GitHub Actions dependencies with read-only workflow permissions

## Local preview

Run the source server with:

```bash
make serve
```

Open <http://127.0.0.1:4180/>.

## Verification and production build

```bash
make check
make build
```

`make check` validates the source. `make build` runs those checks and creates
the deployable `dist/` bundle. Preview that exact production output with:

```bash
make serve-dist
```

The build fingerprints CSS, JavaScript and images. HTML is never cached;
fingerprinted assets may safely be cached as immutable for one year without
mixing a new document with stale styles.

The Open Graph and Twitter metadata reference a dedicated 1200×630 social card
for rich link previews.

## Repository layout

- [`../index.html`](../index.html), [`../legal.html`](../legal.html): source pages
- [`../assets/`](../assets/): source styles, scripts, images and build tooling
- [`../assets/scripts/build_site.py`](../assets/scripts/build_site.py): production builder
- [`../assets/scripts/check_site.py`](../assets/scripts/check_site.py): source checks
- [`../scripts/`](../scripts/): release-profile and workflow-support checks
- [`../Makefile`](../Makefile): local preview, build and validation entry points
- [`../.github/workflows/verify.yml`](../.github/workflows/verify.yml): CI verification workflow
- [`../.github/workflows/publish-github.yml`](../.github/workflows/publish-github.yml): GitHub Pages publication workflow
- [`../.github/workflows/publish-official.yml`](../.github/workflows/publish-official.yml): protected official publication workflow
- `dist/`: generated deployment bundle; do not edit it by hand

## Production safety

Only the generated `dist/` bundle is deployed. DNS, mail routing, certificates
and `.well-known` content remain outside the replacement scope.

See [hosting operations](hosting.md) for the documented Cloudflare edge-cache
safety control and its operational boundary. The protected publication path is
documented in [release-publication.md](release-publication.md).

## Publication targets

- **Publish Official** is the protected Namecheap/Cloudflare publication path for [claudiuschuster.de](https://claudiuschuster.de/).
- **Publish GitHub** builds the same `dist/` bundle and deploys it as a GitHub Pages artifact. The repository Pages mirror is available at <https://claudiuschuster.github.io/claudiuschuster.de/>; canonical metadata continues to point to the official domain.

## Documentation map

- [Hosting operations](hosting.md): provider boundary, Cloudflare cache safety and hosting invariants.
- [Site release](release-publication.md): protected release workflow, environment contract and validation sequence.

Add future development or operations notes under `docs/` and link them from this entry point so the root README remains a focused showcase.

## License

The code is available under the [MIT License](../LICENSE).
