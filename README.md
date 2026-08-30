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
make check
```

The root page and `/en.html` are the combined production candidates. The individual concept pages remain available as design references during review.

## Production safety

Production replacement remains blocked until the local backup, restore verification and final website review are complete and an explicit deployment approval is given. DNS, mail routing, certificates and `.well-known` content remain outside the replacement scope.
