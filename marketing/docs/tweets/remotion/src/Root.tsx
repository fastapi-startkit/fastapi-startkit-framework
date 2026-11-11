import { Composition, staticFile } from "remotion";
import { NarratedVideo, type Timeline, takeFrames } from "./NarratedVideo";

const empty: Timeline = { fps: 30, takes: [] };

export const Root = () => (
  <Composition
    id="NarratedVideo"
    component={NarratedVideo}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={1}
    defaultProps={{ timeline: empty }}
    calculateMetadata={async () => {
      const timeline: Timeline = await fetch(staticFile("timeline.json")).then((response) => response.json());
      const frames = timeline.takes.reduce((sum, take) => sum + takeFrames(take, timeline.fps), 0);
      return { fps: timeline.fps, durationInFrames: Math.max(1, frames), props: { timeline } };
    }}
  />
);
