import React from "react";
import { Composition, Still } from "remotion";
import { Promo, TOTAL_FRAMES } from "./Promo";
import { FPS } from "./theme";
import { Thumbnail } from "./Thumbnail";

export const Root: React.FC = () => (
  <>
    <Composition id="Promo" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} />
    <Still id="Thumbnail" component={Thumbnail} width={1280} height={720} />
  </>
);
