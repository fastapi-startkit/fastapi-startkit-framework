import React from "react";
import { Series } from "remotion";
import { Artisan, CallToAction, Configuration, Frontend, Hook, Install, Orm, Providers, Routing } from "./scenes";
import { FPS } from "./theme";

export const SCENES: [React.FC, number][] = [
  [Hook, 6],
  [Install, 6],
  [Providers, 11],
  [Configuration, 9],
  [Routing, 10],
  [Orm, 11],
  [Artisan, 10],
  [Frontend, 11],
  [CallToAction, 8],
];

export const TOTAL_FRAMES = SCENES.reduce((sum, [, seconds]) => sum + seconds * FPS, 0);

export const Promo: React.FC = () => (
  <Series>
    {SCENES.map(([Scene, seconds], index) => (
      <Series.Sequence key={index} durationInFrames={seconds * FPS}>
        <Scene />
      </Series.Sequence>
    ))}
  </Series>
);
