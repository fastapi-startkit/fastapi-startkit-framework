import { spawnSync } from "node:child_process";
import { copyFileSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const [folder] = process.argv.slice(2);
if (!folder) {
  console.error("Usage: npm run thumbnail <episode dir>");
  process.exit(1);
}

const episodeDir = resolve(process.env.INIT_CWD ?? process.cwd(), folder);
const episode = JSON.parse(readFileSync(join(episodeDir, "episode.json"), "utf8"));
copyFileSync(join(episodeDir, "thumbnail-frame.png"), join(import.meta.dirname, "public", "frame.png"));

const props = {
  number: episode.number,
  title: episode.thumbnail?.title ?? episode.title,
  series: episode.thumbnail?.series ?? "Build an Issue Tracker",
  frame: "frame.png",
};

const result = spawnSync(
  "npx",
  ["remotion", "still", "src/index.ts", "EpisodeThumbnail", join(episodeDir, "thumbnail.png"), `--props=${JSON.stringify(props)}`],
  { cwd: import.meta.dirname, stdio: "inherit" },
);
process.exit(result.status ?? 1);
