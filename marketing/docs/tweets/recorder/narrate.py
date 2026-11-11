# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.28"]
# ///
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import wave
from collections.abc import Callable
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
VOICE = json.loads((ROOT / "voice.json").read_text())
GEMINI = f"https://generativelanguage.googleapis.com/v1beta/models/{VOICE['model']}:generateContent"
OPENROUTER = "https://openrouter.ai/api/v1/audio/speech"
DOTENV = ROOT.parents[2] / ".env"
GAP = 0.15
LEAD = 0.4
TAIL = 1.0
LOUDNESS = -19.0
PEAK = 0.84


def secret(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    for line in DOTENV.read_text().splitlines() if DOTENV.exists() else []:
        name, _, value = line.partition("=")
        if name.strip() == key and value.strip():
            return value.strip().strip("\"'")
    return None


def post(client: httpx.Client, url: str, body: dict) -> httpx.Response:
    for attempt in range(8):
        response = client.post(url, json=body)
        if response.status_code not in (429, 500, 502, 503):
            break
        wait = float(response.headers.get("retry-after", 0)) or min(60, 5 * 2**attempt)
        print(f"  {response.status_code}, retrying in {wait:.0f}s", flush=True)
        time.sleep(wait)
    response.raise_for_status()
    return response


def as_wav(pcm: bytes, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm)
    return buffer.getvalue()


def via_openrouter(client: httpx.Client, text: str) -> bytes:
    body = {
        "model": f"google/{VOICE['model']}",
        "input": text,
        "voice": VOICE["voice"],
        "instructions": VOICE["style"],
        "response_format": "pcm",
    }
    return as_wav(post(client, OPENROUTER, body).content)


def via_gemini(client: httpx.Client, text: str) -> bytes:
    body = {
        "contents": [{"role": "user", "parts": [{"text": text, "speech_metadata": {"style": VOICE["style"]}}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"voice": VOICE["voice"]}},
        },
    }
    data = post(client, GEMINI, body).json()
    return base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])


def speaker() -> tuple[httpx.Client, Callable[[httpx.Client, str], bytes]]:
    if key := secret("OPEN_ROUTER_KEY"):
        return httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=180), via_openrouter
    if key := secret("GEMINI_API_KEY"):
        return httpx.Client(headers={"x-goog-api-key": key}, timeout=180), via_gemini
    sys.exit("Set OPEN_ROUTER_KEY or GEMINI_API_KEY first.")


def duration(file: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(file)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout)


def voice_beats(folder: Path, episode: dict) -> None:
    narration = folder / "narration"
    narration.mkdir(exist_ok=True)
    client, synthesize = speaker()
    with client:
        for take in episode["takes"]:
            for beat in take["beats"]:
                wav = narration / f"{take['name']}-{beat['cue']}.wav"
                sidecar = wav.with_suffix(".txt")
                if not (wav.exists() and sidecar.exists() and sidecar.read_text() == beat["say"]):
                    print(f"voicing {wav.name}", flush=True)
                    wav.write_bytes(synthesize(client, beat["say"]))
                    sidecar.write_text(beat["say"])
                wav.with_suffix(".json").write_text(json.dumps({"seconds": round(duration(wav), 3)}) + "\n")


def place(folder: Path, take: dict, cues: dict[str, float]) -> list[tuple[Path, float, float]]:
    placed = []
    previous_end = LEAD - GAP
    for beat in take["beats"]:
        wav = folder / "narration" / f"{take['name']}-{beat['cue']}.wav"
        length = duration(wav)
        at = max(LEAD + cues[beat["cue"]] + beat.get("offset", 0.0), previous_end + GAP)
        placed.append((wav, at, length))
        previous_end = at + length
    return placed


def gain(file: Path) -> float:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(file), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    mean = float(re.search(r"mean_volume: (-?[\d.]+) dB", result.stderr).group(1))
    return LOUDNESS - mean


def span(folder: Path, take: dict) -> tuple[Path, list[tuple[Path, float, float]], float, float, float]:
    clip = folder / "recordings" / f"{take['name']}.mp4"
    cues = json.loads((folder / "recordings" / f"{take['name']}.cues.json").read_text())
    placed = place(folder, take, cues)
    seconds = duration(clip)
    hold = max(0.0, placed[-1][1] + placed[-1][2] + TAIL - seconds - LEAD)
    return clip, placed, seconds, hold, LEAD + seconds + hold


def timeline(folder: Path, episode: dict) -> None:
    leveled = folder / "narration" / "leveled"
    leveled.mkdir(exist_ok=True)
    takes = []
    for take in episode["takes"]:
        clip, placed, seconds, hold, total = span(folder, take)
        beats = []
        for wav, at, _ in placed:
            target = leveled / wav.name
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                 "-af", f"aresample=48000,volume={gain(wav):.2f}dB,alimiter=limit={PEAK}:level=0", str(target)],
                check=True,
            )
            beats.append({"audio": target.relative_to(folder).as_posix(), "at": round(at, 3)})
        takes.append({
            "name": take["name"],
            "clip": clip.relative_to(folder).as_posix(),
            "lead": LEAD,
            "seconds": round(seconds, 3),
            "hold": round(hold, 3),
            "beats": beats,
        })
    (folder / "timeline.json").write_text(json.dumps({"fps": 30, "takes": takes}, indent=1) + "\n")
    print(json.dumps({"timeline": round(sum(take["lead"] + take["seconds"] + take["hold"] for take in takes), 2)}))


def sync(folder: Path, take: dict) -> Path:
    target = folder / "recordings" / f"{take['name']}.narrated.mp4"
    clip, placed, seconds, hold, total = span(folder, take)
    inputs = ["-i", str(clip)]
    filters = [f"[0:v]tpad=start_mode=clone:start_duration={LEAD}:stop_mode=clone:stop_duration={hold:.2f}[v]"]
    for index, (wav, at, _) in enumerate(placed, start=1):
        inputs += ["-i", str(wav)]
        delay = int(at * 1000)
        filters.append(f"[{index}:a]aresample=48000,volume={gain(wav):.2f}dB,adelay={delay}|{delay}[a{index}]")
    labels = "".join(f"[a{index}]" for index in range(1, len(placed) + 1))
    filters.append(f"{labels}amix=inputs={len(placed)}:normalize=0,alimiter=limit={PEAK}:level=0,apad,atrim=0:{total:.3f}[a]")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", *inputs,
            "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
            "-r", "30", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
            "-t", f"{total:.3f}", "-movflags", "+faststart", str(target),
        ],
        check=True,
    )
    print(json.dumps({"take": take["name"], "seconds": round(total, 2), "beats": [round(at, 2) for _, at, _ in placed]}))
    return target


def join(parts: list[Path], target: Path) -> None:
    inputs = [argument for part in parts for argument in ("-i", str(part))]
    streams = "".join(f"[{index}:v][{index}:a]" for index in range(len(parts)))
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", *inputs,
            "-filter_complex", f"{streams}concat=n={len(parts)}:v=1:a=1[v][a]",
            "-map", "[v]", "-map", "[a]",
            "-r", "30", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
            "-movflags", "+faststart", str(target),
        ],
        check=True,
    )


def main(folder: Path, step: str) -> None:
    episode = json.loads((folder / "episode.json").read_text())
    voice_beats(folder, episode)
    if step == "voice":
        return
    if step == "timeline":
        timeline(folder, episode)
        return
    parts = [sync(folder, take) for take in episode["takes"]]
    if step == "takes":
        return
    target = folder.parent / f"{folder.parent.name}.mp4"
    join(parts, target)
    print(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,sample_rate,duration",
         "-show_entries", "format=duration,size", "-of", "compact", str(target)],
        capture_output=True, text=True, check=True,
    ).stdout)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else "render")
