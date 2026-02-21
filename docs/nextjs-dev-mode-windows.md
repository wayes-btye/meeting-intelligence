# Next.js Dev Mode on Windows — Research Notes

**Date:** 2026-02-21
**Context:** `next dev` (webpack) serves unstyled HTML locally on Windows — CSS and core chunks (`main-app.js`, `app-pages-internals.js`) return 404 despite pages compiling successfully.

---

## What We Observed

- `npm run dev` starts, pages compile (`✓ Compiled /login in 7.1s, 694 modules`)
- Page HTML is served (HTTP 200) and references `/_next/static/css/app/layout.css`
- Browser requests for CSS and JS chunks all return 404
- Files are partially written to `.next/static/chunks/` (e.g. `webpack.js` exists) but core bundles (`main-app.js`, `app-pages-internals.js`) and CSS are absent from disk
- `next build && next start` works perfectly — all assets compiled to content-hashed files, fully served

## Root Cause (Working Theory)

Next.js 14 App Router uses a **two-pass webpack compilation** in dev mode:
1. **Server pass** — compiles Server Components, produces HTML
2. **Client pass** — compiles Client Components + CSS (triggered lazily)

On Windows with Next.js 14 (webpack bundler), the client-pass output doesn't register correctly in webpack's in-memory output filesystem. The HTML embeds references to these chunks, but when the browser requests them the dev server can't find them.

This may be exacerbated by Windows Defender or other antivirus holding file locks during rapid compilation (Next.js docs specifically call out antivirus as a Windows dev performance issue).

## What Next.js Recommends (from official docs, Feb 2026)

From https://nextjs.org/docs/app/guides/local-development:

1. **Upgrade to Next.js 15 + use Turbopack** — Turbopack is now the stable default bundler for `next dev`. It has significantly better HMR performance and avoids the webpack two-pass issue entirely.

2. **Add project folder to Windows Defender exclusion list** — Antivirus scanning `.next/` during compilation can cause file lock conflicts and slow/broken HMR. Steps:
   - Open Windows Security → Virus & threat protection → Manage settings → Add or remove exclusions
   - Add `C:\meeting-intelligence\` as a Folder exclusion

3. **Avoid Docker for dev on Windows** — Docker filesystem on Windows causes HMR delays of seconds to minutes (not our issue, noted for completeness).

## Potential Fixes to Try (in order of effort)

### Option 1: Try Turbopack with current Next.js 14 (low effort)

```bash
cd frontend
npm run dev -- --turbo
```

Next.js 14 supports `--turbo` as an opt-in flag. Turbopack's memory model is different from webpack and may not have the client-chunk registration issue.

**Risk:** Turbopack in 14.x is less stable than in 15.x; some edge cases with certain imports.

### Option 2: Upgrade to Next.js 15 (medium effort)

```bash
cd frontend
npm install next@15 react@19 react-dom@19
npm run dev   # Turbopack is default
```

Next.js 15 uses Turbopack by default for `next dev`. Official docs say it provides "significant performance improvements over webpack" for HMR.

**Risk:** Breaking changes in Next.js 15 — notably React 19 upgrade, `params` becoming async in Server Components, and caching behaviour changes. Requires testing all pages.

Upgrade guide: https://nextjs.org/docs/app/guides/upgrading/version-15

### Option 3: Add project to Windows Defender exclusions (low effort, good idea regardless)

See instructions above. Try with current 14.x webpack dev mode after exclusion. May resolve the file lock issue causing CSS not to be written.

### Option 4: Related known issue — `?v=` query parameter 404s

GitHub issue #73789 documents a similar pattern where `?dpl=<deploymentId>` query params caused 404s for static chunks when using Turbopack. Fixed in latest Next.js. If we upgrade to Next.js 15 this is resolved.

## Current Workaround (in place)

Until one of the above is tried, we use production builds locally:

```bash
cmd //c "taskkill /F /IM node.exe"
cd frontend && npm run build && npm start
```

This is reliable but requires a rebuild after each code change (no HMR). Documented in CLAUDE.md `## Starting the Dev Environment`.

## Resolution — Confirmed Fix

**`npm run dev -- --turbo` works on Windows.** Tested 2026-02-21:
- Turbopack uses a different CSS output path (`static/chunks/app_6cac50._.css`) vs webpack (`static/css/app/layout.css`)
- The webpack path is what 404s; Turbopack's path serves correctly (HTTP 200)
- Full Tailwind CSS applied, hot reload functional
- CLAUDE.md updated to instruct `npm run dev -- --turbo` as the standard local dev command

The `npm run build && npm start` fallback remains documented for edge cases.

**Option 2** (Next.js 15 upgrade, where Turbopack is the default) remains the proper long-term fix.

---

*Sources:*
- [Next.js local development guide](https://nextjs.org/docs/app/guides/local-development)
- [Next.js 15 release notes](https://nextjs.org/blog/next-15)
- [Turbopack dev stable announcement](https://nextjs.org/blog/turbopack-for-development-stable)
- [GitHub issue #73789 — deploymentId + turbo chunk 404](https://github.com/vercel/next.js/issues/73789)
- [Next.js version 15 upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-15)
