# Hosting operations

This document contains no credentials, account usernames, private paths, API tokens, keys, cookies, or hosting session URLs.

## Cloudflare edge-cache safety (2026-09-04)

The `claudiuschuster.de` Cloudflare zone has the enabled response-stage Cache Rule `Upstream no-cache response guard` (`ref: upstream_no_cache_response_guard`, Cloudflare ruleset ID `0b50b4ee3a9d4443959b54c7611b4f6d`, rule ID `0221556cbdd0462292c6a5d91cf6592a`). It matches:

```text
any(http.response.headers["cf-edge-cache"][*] == "no-cache")
```

For matching origin responses it sets Cloudflare-only `no-store`. This prevents a Namecheap/Imunify360 verification response carrying `CF-Edge-Cache: no-cache` from being stored at the edge and served as the website to later visitors. It does not disable or configure Imunify360 at Namecheap; it only protects Cloudflare's cache. Ordinary website responses remain eligible for the normal cache policy.

After creation, only the `claudiuschuster.de` zone cache was purged. Live verification showed the normal page, exact edge/origin content identity, and normal `MISS` to `HIT` caching behavior. Revalidate this guard if Namecheap changes the header name or semantics.
