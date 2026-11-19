# Vendored assets

Served as local static files: no CDN, no third-party requests (brief 4.9).

| File | Source | Licence | Integrity of the npm tarball |
|---|---|---|---|
| `core/static/core/js/htmx-2.0.4.min.js` | `dist/htmx.min.js` from `https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.4.tgz` | 0BSD | `sha512-HLxMCdfXDOJirs3vBZl/ZLoY+c7PfM4Ahr2Ad4YXh6d22T5ltbTXFFkpx9Tgb2vvmWFMbIc3LqN2ToNkZJvyYQ==` (matches the registry's `dist.integrity`) |

To update: download the new tarball from the npm registry, compare its
SHA-512 with `dist.integrity` from `https://registry.npmjs.org/htmx.org/<version>`,
copy `dist/htmx.min.js` under a new versioned name, update the templates
that load it and this table.
