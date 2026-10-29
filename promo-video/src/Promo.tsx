import React from "react";
import { Series } from "remotion";
import { Agents, Artisan, Caching, CallToAction, CreateProject, Frontend, Hook, Installer, Orm, Providers, Routing } from "./scenes";
import { FPS } from "./theme";

export const SCENES: [React.FC, number][] = [
  [Hook, 5],
  [CreateProject, 6],
  [Installer, 13],
  [Providers, 9],
  [Routing, 8],
  [Orm, 9],
  [Artisan, 12],
  [Caching, 9],
  [Agents, 8],
  [Frontend, 8],
  [CallToAction, 6],
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
