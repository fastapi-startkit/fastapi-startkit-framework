# Tweets

Each folder is one thread. `NNN-thread.md` is the exact text to post, plus the image to attach.

```
001-installations/
  003-thread.md                        tweet text + ![](images/003.png)
  cards/003/providers/app_provider.py  code on the card; the path under 003/ is the window title
  images/003.png                       generated
```

A card folder with several files renders `NNN-1.png`, `NNN-2.png`, … in file-name order. Shell files are titled `Terminal`.

Render the images after editing a card:

```bash
uv run docs/tweets/render.py docs/tweets/001-installations
```

Code is set in Dank Mono when it is installed (`~/Library/Fonts`, `/Library/Fonts`, or `TWEET_FONT_DIR`). Otherwise the bundled JetBrains Mono is used.
