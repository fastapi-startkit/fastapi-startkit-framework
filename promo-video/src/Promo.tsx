import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { Ambient, Footer } from "./components";
import { AddDatabase, Agents, CallToAction, CreateProject, FastapiContext, Frontend, Hook, IndieHacker, Installer, Logging, ModelAndMigration, PainEnvironment, PainLogging, Providers, QueryIt, Routing, RunInBrowser, Testing } from "./scenes";
import { FPS } from "./theme";

export const SCENES: [React.FC, number][] = [
  [FastapiContext, 7],
  [PainLogging, 9],
  [PainEnvironment, 9],
  [IndieHacker, 6],
  [Hook, 5],
  [CreateProject, 6],
  [Installer, 12],
  [RunInBrowser, 8],
  [Providers, 9],
  [Logging, 9],
  [Routing, 8],
  [AddDatabase, 12],
  [ModelAndMigration, 12],
  [QueryIt, 10],
  [Testing, 9],
  [Frontend, 10],
  [Agents, 8],
  [CallToAction, 6],
];

const INTRO_FRAMES = SCENES.slice(0, SCENES.findIndex(([Scene]) => Scene === Hook) + 1).reduce((sum, [, seconds]) => sum + seconds * FPS, 0);

export const TOTAL_FRAMES = SCENES.reduce((sum, [, seconds]) => sum + seconds * FPS, 0);

export const Promo: React.FC = () => (
  <AbsoluteFill>
    <Ambient />
    <Series>
      {SCENES.map(([Scene, seconds], index) => (
        <Series.Sequence
          key={index}
          durationInFrames={seconds * FPS}
          style={{
            scale: 0.986
          }}
        >
          <Scene />
        </Series.Sequence>
      ))}
    </Series>
    <Footer totalFrames={TOTAL_FRAMES} hideBefore={INTRO_FRAMES} hideAfter={TOTAL_FRAMES - SCENES[SCENES.length - 1][1] * FPS} />
  </AbsoluteFill>
);
