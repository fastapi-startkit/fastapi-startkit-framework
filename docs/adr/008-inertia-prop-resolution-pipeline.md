# 008: Inertia prop resolution pipeline

Date: 2026-10-09
Status: Accepted

## Problem

`InertiaResponse.to_response` resolved props in one flat loop. It knew one special prop type (`OptionalProp`), matched partial reloads against top-level keys only, ignored `X-Inertia-Partial-Except`, and emitted no prop metadata. The Inertia v3 protocol needs more prop behaviours: always, deferred (with groups), merge/prepend/deep merge with `matchOn`, once, infinite scroll, rescued failures, nested props with dot-path partial reloads, and `sharedProps`. Bolting each one onto the flat loop would scatter ordering and metadata rules across many `isinstance` branches.

## Alternatives

- **One class per prop type** (`AlwaysProp`, `DeferProp`, `MergeProp`, ...), as in the Laravel adapter. The behaviours combine (a deferred, rescued, merged scroll prop), so this either needs mixins or loses combinations.
- **Extend the flat loop.** It stays top-level only, so nested props and dot paths still do not work.
- **One `Prop` with composable options plus a recursive resolver (chosen).** This mirrors the reference implementation, `inertiajs/inertia-omega`. Every behaviour is an option on the same object, and one recursive pass handles filtering, resolution and metadata at every depth.

## Decision

`fastapi_startkit.inertia.props` gains:

- `Prop(value)`: a value, a nested dict, or a sync/async callable (optionally taking the request). Its chainable builders are `optional()`, `defer(group="default")`, `group(name)`, `always()`, `rescue()`, `merge()`, `deep_merge()`, `append()`, `prepend()`, `append_at(path)`, `prepend_at(path)`, `match_on(key)`, `once()`, `once_as(key)`, `until(ttl)`, `fresh()` and `wrapper(key)`. `OptionalProp` remains as a `Prop` subclass for backwards compatibility.
- `ScrollMetadata` (with `pages()` and `cursors()` constructors), the `ProvidesScrollMetadata` protocol, and `scroll_metadata_of(page)`. `scroll_metadata_of` also reads the ORM `LengthAwarePaginator`/`SimplePaginator` (`current_page`/`previous_page`/`next_page`) and serializes them via `serialize()`.
- `PropsResolver(request, component)`: one recursive resolver that returns the props and the page metadata.

The `Inertia` facade adds `lazy`, `defer`, `always`, `merge`, `deep_merge`, `once`, `scroll`, `scroll_with` and `expose_shared_prop_keys`.

The resolver handles each level of the props tree in order:

1. Build each prop's dot path (`auth.user`).
2. Partial filter. On a partial reload of the same component, a prop survives only if (a) it is `always`, (b) its parent was always or computed, or (c) it matches the request. A prop matches when it leads to or sits within an `X-Inertia-Partial-Data` path, and is not within an `X-Inertia-Partial-Except` path. Except wins over only.
3. Exclusion. Outside partial reloads, optional and deferred props are skipped without running their callbacks. On Inertia visits, once props already listed in `X-Inertia-Except-Once-Props` are skipped too, unless `fresh()`. On partial reloads, already-loaded once props are skipped unless they lead to or sit within an `X-Inertia-Partial-Data` path (`only=settings.theme` reloads once prop `settings`), so an except-only reload does not re-run them. Skipped props still announce `deferredProps`, `mergeProps` (when non-eager) and `onceProps`.
4. Resolve. A dict recurses as nested props. A callable is called and awaited. If it returns a `Prop`, that prop's value is unwrapped (and called) until a plain value remains; the outer prop's options govern. A returned `Prop` that carries options (for example `.merge()`) emits a `UserWarning` naming the path, because those options are ignored. A returned `Prop` chain that references itself raises `ValueError`. A returned dict recurses as computed props: its children are resolved but not partially filtered. An exception fails the response, unless the prop is `rescue()`d; then the prop is dropped, logged, and listed in `rescuedProps`.
5. Collect metadata for included props:
   - Merge, prepend and deep-merge paths. These are skipped for keys in `X-Inertia-Reset`. On partial reloads a merge target is emitted when it sits within a requested path; otherwise the requested paths inside the target are emitted (`only=posts.data` on merge prop `posts` emits `posts.data`). Excepted paths are never emitted.
   - `matchPropsOn` as `path.key`.
   - `scrollProps`, with `reset` taken from `X-Inertia-Reset`.
   - `onceProps` as `{key: {prop, expiresAt}}`, where `expiresAt` is in epoch milliseconds (second precision) or `null`.

Scroll props are merge props. On included scroll props the wrapper key (default `data`) is appended, or prepended when `X-Inertia-Infinite-Scroll-Merge-Intent: prepend`. The wrapper is applied per request, so a shared `Prop` is never mutated. `wrapper()` and `scroll()` can be chained in either order.

Top-level dotted keys (`"auth.user": ...`) are unpacked into nested dicts before resolution, merging into an existing parent as Laravel does. A dict parent is copied and extended. A `Prop` parent is copied with its options kept, and a callable parent is wrapped so it still resolves lazily and the dotted value is merged into its result. A parent that is not a mapping raises `TypeError` naming the path. Containers and props are copied, so shared props are never mutated.

`sharedProps` lists the top-level shared keys. It is on by default, as in omega and the Laravel adapter, and can be disabled with `Inertia.expose_shared_prop_keys(False)`. Empty metadata keys are omitted from the page.

Callbacks are resolved sequentially, not concurrently as in omega. Async ORM sessions are not safe for concurrent use within one request.

`try_lazy` is not added. In Python every callback can raise, so `.rescue()` works on any prop.

## Implementation

- `inertia/props/props.py`: `Prop`, `OptionalProp`, `MergeOptions`, `OnceOptions`, `ScrollOptions`.
- `inertia/props/scroll.py`: scroll metadata and paginator integration.
- `inertia/props/resolver.py`: the resolver and page metadata.
- `inertia/constant.py`: new protocol header names.
- `InertiaResponse.to_response` delegates to the resolver and spreads the metadata into the page after `version`.

## Validation

- Unit tests in `fastapi_startkit/tests/inertia/test_prop_resolution.py` cover every behaviour through the FastAPI `TestClient`, with and without `X-Inertia`, plus resolver-level cases for nested and dot-path partials.
- The existing Inertia tests pass unchanged.
- The full framework suite passes and coverage stays above `fail_under`. `ruff` and `basedpyright` are clean.
