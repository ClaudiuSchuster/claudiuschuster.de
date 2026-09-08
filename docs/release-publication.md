# Static publication

This repository uses a deliberately small publication path for the personal
site. It borrows the security boundary from the OSS Singularity release work,
but does not copy its Commons/API artifact consumer, Worker checks, GitHub App
policy reader, or large provider-observation suite.

## Release boundary

The only automatic production input is the generated dist/ directory from an
exact protected main commit. The workflow has two entry points:

- a successful Verify run on main starts an automatic publish when the
  repository variable PROFILE_PUBLISH_ENABLED is true;
- workflow dispatch supports plan and publish, and is restricted to main.

Before the publisher sends bytes, it rechecks all required checks for the exact
commit: Static site, Analyze (actions), Analyze (javascript-typescript),
Analyze (python), and CodeQL. On a post-merge push, GitHub's CodeQL default
setup may expose the three exact-commit Analyze runs without the PR-only
`CodeQL` aggregate; the gate accepts that fallback only when all three are
completed successfully and never bypasses a present aggregate failure. The
job uses a protected production-static environment and a non-canceling
concurrency group.

The remote target is not a shell. Its maintenance identifier is
`claudiuschuster_de_target`; it is deliberately domain-derived but is not a
hostname. A dedicated SSH key accepts only the stable transport command
`claudiuschuster_de_release_v1`. The installed endpoint:

1. validates the candidate paths, sizes, hashes and pinned .htaccess;
2. keeps provider-managed .well-known content outside the candidate;
3. creates a private backup and an isolated stage tree;
4. switches the document root by two guarded renames;
5. retains the preceding tree for rollback;
6. exposes no arbitrary path, command, SFTP or forwarding operation.

After the switch, the client uses a Cloudflare token that can purge only the
claudiuschuster.de zone and verifies the homepage, a fingerprinted asset, the
www redirect, the direct origin and the edge MISS-to-HIT transition. The edge
and origin byte checks allow a bounded convergence window with fresh query
probes after the atomic switch; a persistent mismatch still causes the same
attempt identity to be used for one guarded rollback and a second zone-local
purge.

The workflow contains no cPanel account token, operator SSH key, GitHub App
private key or Cloudflare account-wide credential. The OSS Singularity release
reader belongs to that organization and is intentionally not reused by this
personal repository.

## Environment contract

Create a GitHub environment named production-static and restrict its
deployment branch policy to main. Configure only the following values; never
commit them or print them in a job:

| Kind | Name | Meaning |
| --- | --- | --- |
| Environment secret | PROFILE_SSH_KEY | Dedicated Ed25519 private key for this target |
| Environment secret | PROFILE_SSH_USER | cPanel account user used by the forced command |
| Environment secret | PROFILE_ORIGIN_IP | Current direct Stellar origin address |
| Environment secret | CF_RELEASE_TOKEN | Cloudflare token scoped only to this zone's cache purge |
| Environment variable | PROFILE_SSH_PORT | The verified Namecheap SSH port |
| Environment variable | PROFILE_SSH_HOST_KEY | Pinned ssh-ed25519 host key, without a hostname |
| Environment variable | PROFILE_RUNTIME_SHA256 | SHA-256 of the installed remote endpoint |
| Repository variable | PROFILE_PUBLISH_ENABLED | true only after the private target pilot is complete |

The private endpoint configuration, state, backups and retained rollback
trees live outside the public document root. The bootstrap operator resolves
the authenticated addon-domain root first and records the current .htaccess
hash. It must preserve the existing .well-known tree, including provider
SSL-manager files. A changed .htaccess requires a deliberate operator
re-bootstrap; a normal content release cannot smuggle a server-policy change.

## Validation sequence

1. Run make check, make build and scripts/test-profile-release.py locally.
2. Resolve the exact addon-domain mapping through authenticated cPanel
   inventory. Record the live manifest, .well-known tree, origin, DNS and
   sibling-root boundary before the first write.
3. Install the reviewed remote endpoint in a private account directory and
   bootstrap one private control directory for this root.
4. Add the dedicated forced-command key, then prove status works while shell,
   PTY, forwarding and extra-command requests fail.
5. Set the environment values, keep PROFILE_PUBLISH_ENABLED false, and run
   workflow dispatch plan against the current main.
6. Review the plan and the PR. Enable the repository variable only after the
   plan, remote status, provider audit and rollback proof are green.
7. Merge through the protected PR path. Let the successful Verify
   workflow_run start the first automatic publication. Capture its sanitized
   summary and independently compare the exact merge SHA with the live
   manifest.

The automatic path never deploys a branch checkout, unmerged dist/ tree or
runner-created secret. A lost remote response is unresolved state, not proof
that no change happened; inspect the original identity before retrying.

## Handoff for BoundInLove

The same pattern can be prepared for the BoundInLove repository, but it needs
its own target binding:

- use a separate workflow copy with the BoundInLove repository name and ID;
- use a separate forced-command SSH key, target identifier and private control root;
- resolve boundinlove.xxx through cPanel inventory instead of assuming the
  main-domain path;
- use a separate Cloudflare zone token and fixed zone ID;
- preserve that site's provider-managed .well-known and any approved
  server-configuration overlay;
- pin the installed endpoint digest in that repository's environment;
- use a domain-derived target identifier and bootstrap the private target
  record before the first workflow plan;
- keep PROFILE_PUBLISH_ENABLED off until plan, live acceptance and rollback
  have all passed.

For a small static homepage, copy only the workflow, profile-publish client,
check-release helper, remote endpoint, fixture test and this document.
Replace the target constants and environment names, not the credentials.
The larger OSS workflow remains the reference for a site with generated
artifacts, API compatibility or multiple production stages; it is not a
requirement for BoundInLove's static homepage.
