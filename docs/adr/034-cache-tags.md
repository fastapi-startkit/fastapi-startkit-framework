---
title: Tagged cache entries with Cache.tags()
date: 2026-10-21
---

## Problem

Applications cache many related entries (every page of a user's posts, every report for a team) and need to invalidate the whole group at once without knowing every key. Laravel offers `Cache::tags([...])`: entries written through a tagged cache can be read only with the same tags, and `Cache::tags([...])->flush()` invalidates every entry that carries any of those tags. The cache module has no grouping, and `flush()` clears the whole store.

## Alternatives

- **Store a key list per tag and delete each key on flush.** Every store needs a list or set type and an atomic append, and the file and database stores have neither. Lists also grow without bound for keys that expire. Rejected.
- **Scan keys by pattern on flush.** Not possible for the file store (keys are hashed) and slow for the database. Rejected.
- **Namespaced keys (Laravel's original tagged cache).** Each tag has a random version id stored in the cache. A tagged entry's key is prefixed with a hash of its tags' ids. Flushing a tag writes a new id, so old entries can no longer be addressed. Works on every store with plain `get`/`put`. Chosen.

## Decision

- `cache/tagged_store.py` adds `TagSet(store, names, key)` and `TaggedStore(store, tags)`.
  - `TagSet` keeps the names deduplicated and sorted, so `tags(["a", "b"])` and `tags(["b", "a"])` address the same entries (Laravel is order-sensitive; sorting removes that trap). The id of tag `name` lives in the wrapped store under the repository key `tag:<name>:key` (`<prefix>:tag:<name>:key` with a prefix), stored forever, and is created as a random hex token on first use. `namespace()` returns the SHA-1 of the ids joined with `|`; `reset()` writes a new id for every tag.
  - `TaggedStore` implements the store contract over the wrapped store. `get`, `put` and `forget` use the key `<prefix>:<namespace>:<key>` (`<namespace>:<key>` without a prefix). The prefix comes first, as in Laravel, so a store that flushes by prefix, such as the Redis store's `SCAN <prefix>:*`, still reaches tagged entries. `flush` resets the tags instead of flushing the store.
  - Tag ids share the user key space: `tag:<name>:key` is an ordinary cache key, so `Cache.put("tag:people:key", ...)` or `Cache.forget(...)` on it changes or resets that tag. Avoid user keys of that form.
- `Repository.tags(names)` accepts a string or a sequence of strings and returns an unprefixed `Repository` over `TaggedStore`, which applies the prefix itself, so every repository method (`get`, `put`, `remember`, the decorator, ...) works tagged. It wraps whatever store the repository has, so `Cache.memo().tags(...)` and `Cache.store("file").tags(...)` work too. An empty tag list raises `ValueError`. A tagged repository has no `lock` and raises `TypeError`.
- Flushed entries are not deleted; they stay in the store until they expire or the store is flushed. Use a TTL on tagged entries in long-lived stores. If two workers create a tag's first id at the same time, the last write wins, and entries the other worker wrote under its id become misses. That only costs a recompute.
- Reading a tagged entry costs one extra store read per tag.
- The facade reaches `tags` through the manager; the stub adds `tags`.

## Usage

```python
from fastapi_startkit.facades import Cache

await Cache.tags(["people", "artists"]).put("john", john, 600)
john = await Cache.tags(["people", "artists"]).get("john")

posts = await Cache.tags("posts").remember(f"user:{user_id}", 600, load_posts)

await Cache.tags("people").flush()
```

## Validation

`tests/cache/test_tagged_store.py` (unittest, array, file and in-memory SQLite database stores): the tagged key is `<prefix>:<sha1>:<key>`, tagged put/get round-trips and untagged or differently tagged reads miss; tag order and duplicates do not matter; flushing one tag invalidates every entry carrying it and keeps entries without it, and keeps untagged entries; tag ids persist in the store and are prefixed; forget removes only the tagged key; `remember` and the decorator work tagged; a string tag is accepted; an empty list raises; `tags().lock()` raises `TypeError`; tags work on a memo repository.
