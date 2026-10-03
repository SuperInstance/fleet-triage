# Vendored @quilt/core dist — provenance

Built from `SuperInstance/quilt` branch **`playtest-classes-10-11`**
(PR #28, stacks on PR #27 `playtest-gold-r2`), which carries play-test
fix classes 1–11 plus the eager-reactive iteration.

- Source commit: see `git log` in the quilt repo for branch tip at build time
- Build: `npm ci && npm run build` in `packages/core` (tsc → `dist/`)
- Package identity: `@quilt/core@0.3.0`, ESM, sole runtime dep `yaml`
- The eleven tools in this repo were verified green against exactly this dist
  (94/94 checks, offline mode; re-verified live 2026-09-30 after the
  convergence-gauge #28 merge)

## Rebuild after upstream lands

```sh
git clone -b playtest-classes-10-11 https://github.com/SuperInstance/quilt /tmp/quilt
cd /tmp/quilt/packages/core && npm ci && npm run build
rm -rf vendor/quilt-core/dist && cp -r /tmp/quilt/packages/core/dist vendor/quilt-core/dist
```

Once PRs #27 + #28 merge to `main`, rebuild from `main` and delete this file's
branch note.
