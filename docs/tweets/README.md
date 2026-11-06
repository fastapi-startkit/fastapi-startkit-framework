# Tweets

Each folder is one thread. `NNN-thread.md` is the exact text to post, plus the image to attach.

```
001-installations/
  001-thread.md      tweet text + ![](images/001.png)
  cards/003.py       code shown on the card
  images/003.png     generated
```

Render the images after editing a card:

```bash
uv run docs/tweets/render.py docs/tweets/001-installations
```

Code is set in Dank Mono when it is installed (`~/Library/Fonts`, `/Library/Fonts`, or `TWEET_FONT_DIR`). Otherwise the bundled JetBrains Mono is used.
