---
title: Generated outline and Digging Deeper placement for the Authentication docs page
date: 2026-10-07
---

## Why

`docs/authentication.md` in the docs site carried a hand-written "Contents" list that duplicates the heading structure, so it drifts whenever a section is added or renamed. VitePress already generates an "On this page" outline from headings, and the page frontmatter already sets `outline: deep`. Separately, the Authentication sidebar entry sat under "Guide" although the page is a feature reference like Storage, Queues and Broadcasting, which live under "Digging Deeper". The page has no "Digging Deeper" heading of its own, so the request to move authentication "down to digging deeper" applies to the sidebar.

## How

- Delete the "## Contents" section from `docs/authentication.md`; the existing `outline: deep` frontmatter drives the generated outline (h2 to h6). Other pages are untouched, so no global `themeConfig.outline` change.
- In `.vitepress/config.mts`, move `{ text: 'Authentication', link: '/docs/authentication' }` from the "Guide" group to the start of the "Digging Deeper" group. The URL does not change, so no links break.

## Verification

`npm run docs:build` succeeds with no dead links, and the built page has no "Contents" heading but still renders the outline aside.
