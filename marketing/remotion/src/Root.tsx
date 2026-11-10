import React from "react";
import { Still } from "remotion";
import { EpisodeThumbnail, EpisodeThumbnailProps } from "./EpisodeThumbnail";

const defaults: EpisodeThumbnailProps = { number: 1, title: "What are we building?", series: "Build an Issue Tracker", frame: "frame.png" };

export const Root: React.FC = () => <Still id="EpisodeThumbnail" component={EpisodeThumbnail} defaultProps={defaults} width={1280} height={720} />;
