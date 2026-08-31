# Contributing

Thanks for taking the time to improve claudiuschuster.de.

## Before making a change

Open an issue or discussion before substantial visual, architectural or content changes. Small, focused fixes may go directly to a pull request.

Please preserve the project's defining constraints:

- no runtime dependencies, tracking, cookies or remote scripts
- progressive enhancement and useful content without JavaScript
- equivalent behavior in German and English
- keyboard access, visible focus and reduced-motion support
- deterministic, cache-safe production output

## Verify locally

Run the repository checks and production build:

```bash
git diff --check
make build
```

If Node.js is available, also parse the source and generated JavaScript:

```bash
node --check assets/theme-boot.js
node --check assets/theme-switcher.js
node --check dist/assets/theme-boot.*.js
node --check dist/assets/theme-switcher.*.js
```

Visual changes should be reviewed in both design worlds, both languages and relevant desktop and mobile widths. Mention that review in the pull request.

## Pull requests

Keep commits and pull requests focused. Explain the user-visible effect, operational impact and verification performed. Generated `dist/` output and local review artifacts are intentionally not committed.
