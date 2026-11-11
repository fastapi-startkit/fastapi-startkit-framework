import { spawnSync } from "node:child_process";
import { basename, dirname, resolve } from "node:path";

const [folder] = process.argv.slice(2);
if (!folder) {
  console.error("Usage: npm run render <video dir>");
  process.exit(1);
}

const publicDir = resolve(process.env.INIT_CWD ?? process.cwd(), folder);
const output = resolve(publicDir, `${basename(dirname(publicDir))}.mp4`);
const result = spawnSync(
  "npx",
  ["remotion", "render", "src/index.ts", "NarratedVideo", output, `--public-dir=${publicDir}`, "--codec=h264"],
  { cwd: import.meta.dirname, stdio: "inherit" },
);
process.exit(result.status ?? 1);
