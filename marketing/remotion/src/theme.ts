import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadLocalFont } from "@remotion/fonts";
import { staticFile } from "remotion";

const sans = loadInter("normal", { weights: ["600", "800"], subsets: ["latin"] }).fontFamily;
const fallbackMono = "JetBrains Mono";
loadLocalFont({ family: fallbackMono, url: staticFile("fonts/JetBrainsMono-Regular.woff2"), weight: "400" });
loadLocalFont({ family: fallbackMono, url: staticFile("fonts/JetBrainsMono-SemiBold.woff2"), weight: "600" });

export const theme = {
  bg: "#0d1117",
  panel: "#161b22",
  border: "#30363d",
  text: "#e6edf3",
  muted: "#7d8590",
  blue: "#2f81f7",
  green: "#3fb950",
  sans: `${sans}, -apple-system, 'Segoe UI', sans-serif`,
  mono: `"Dank Mono", "${fallbackMono}", Menlo, monospace`,
};
