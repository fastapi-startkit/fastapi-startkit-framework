import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadLocalFont } from "@remotion/fonts";
import { loadFont as loadSpaceGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { staticFile } from "remotion";

const display = loadSpaceGrotesk("normal", { weights: ["500", "700"], subsets: ["latin"] }).fontFamily;
const sans = loadInter("normal", { weights: ["400", "500", "600"], subsets: ["latin"] }).fontFamily;
const mono = "JetBrains Mono";
loadLocalFont({ family: mono, url: staticFile("fonts/JetBrainsMono-Regular.woff2"), weight: "400" });
loadLocalFont({ family: mono, url: staticFile("fonts/JetBrainsMono-SemiBold.woff2"), weight: "600" });

export const theme = {
  bg: "#0b1020",
  panel: "#111a2e",
  panelBorder: "#24314f",
  boxBorder: "#56688f",
  text: "#e6edf7",
  muted: "#8a9bbd",
  accent: "#22c55e",
  accent2: "#38bdf8",
  keyword: "#c084fc",
  string: "#86efac",
  number: "#fbbf24",
  func: "#60a5fa",
  type: "#f472b6",
  comment: "#64748b",
  decorator: "#fb923c",
  display: `${display}, ${sans}, sans-serif`,
  sans: `${sans}, 'Helvetica Neue', Arial, sans-serif`,
  mono: `"${mono}", Menlo, monospace`,
  gradient: "linear-gradient(90deg, #22c55e 0%, #38bdf8 100%)",
};

export const FPS = 30;
