## Summary

- Describe the user-visible or operational change.
- Explain why this is the smallest useful solution.

## Verification

- [ ] `git diff --check`
- [ ] `make build`
- [ ] JavaScript parse checks when scripts changed
- [ ] Both languages and design worlds reviewed when UI or content changed
- [ ] Relevant desktop and mobile widths reviewed when layout changed
- [ ] Accessibility and reduced-motion behavior reviewed when interaction changed

## Safety

- [ ] No tracking, cookies, remote scripts or runtime dependencies added
- [ ] No private information included in code, screenshots or logs
- [ ] Production deployment scope remains limited to the generated `dist/` bundle
