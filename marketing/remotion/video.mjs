import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";

const [folder, ...takes] = process.argv.slice(2);
if (!folder) {
  console.error("Usage: npm run video <episode dir> [take ...]");
  process.exit(1);
}

const episodeDir = resolve(process.env.INIT_CWD ?? process.cwd(), folder);
const recorder = join(import.meta.dirname, "..", "vscode-recordings");

for (const step of [["record.py", episodeDir, ...takes], ["narrate.py", episodeDir]]) {
  const result = spawnSync("uv", ["run", ...step], { cwd: recorder, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
