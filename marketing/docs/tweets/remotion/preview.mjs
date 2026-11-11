import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const [folder] = process.argv.slice(2);
if (!folder) {
  console.error("Usage: npm run preview <video dir>");
  process.exit(1);
}

const publicDir = resolve(process.env.INIT_CWD ?? process.cwd(), folder);
const result = spawnSync("npx", ["remotion", "studio", "src/index.ts", `--public-dir=${publicDir}`], {
  cwd: import.meta.dirname,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
