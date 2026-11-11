import { AbsoluteFill, Audio, Freeze, OffthreadVideo, Sequence, Series, staticFile } from "remotion";

export type Beat = { audio: string; at: number };
export type Take = { name: string; clip: string; lead: number; seconds: number; hold: number; beats: Beat[] };
export type Timeline = { fps: number; takes: Take[] };

const frames = (seconds: number, fps: number) => Math.round(seconds * fps);

export const takeFrames = (take: Take, fps: number) =>
  frames(take.lead, fps) + frames(take.seconds, fps) + frames(take.hold, fps);

const TakeClip = ({ take, fps }: { take: Take; fps: number }) => {
  const lead = frames(take.lead, fps);
  const body = frames(take.seconds, fps);
  const hold = frames(take.hold, fps);
  const video = <OffthreadVideo src={staticFile(take.clip)} muted />;
  return (
    <AbsoluteFill style={{ backgroundColor: "#0d1117" }}>
      <Sequence durationInFrames={lead} name="lead">
        <Freeze frame={0}>{video}</Freeze>
      </Sequence>
      <Sequence from={lead} durationInFrames={body} name={take.name}>
        {video}
      </Sequence>
      {hold > 0 && (
        <Sequence from={lead + body} durationInFrames={hold} name="hold">
          <Freeze frame={body - 1}>{video}</Freeze>
        </Sequence>
      )}
      {take.beats.map((beat) => (
        <Sequence key={beat.audio} from={frames(beat.at, fps)} name={beat.audio.split("/").pop()}>
          <Audio src={staticFile(beat.audio)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const NarratedVideo = ({ timeline }: { timeline: Timeline }) => (
  <Series>
    {timeline.takes.map((take) => (
      <Series.Sequence key={take.name} durationInFrames={takeFrames(take, timeline.fps)} name={take.name}>
        <TakeClip take={take} fps={timeline.fps} />
      </Series.Sequence>
    ))}
  </Series>
);
