import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

RATE = 44100
BPM = 120
BEAT = 60 / BPM
BAR = BEAT * 4
PROGRESSION = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
rng = np.random.default_rng(7)


def hz(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def lowpass(signal: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, cutoff, "low", fs=RATE, output="sos"), signal)


def highpass(signal: np.ndarray, cutoff: float) -> np.ndarray:
    return sosfilt(butter(2, cutoff, "high", fs=RATE, output="sos"), signal)


def bandpass(signal: np.ndarray, low: float, high: float) -> np.ndarray:
    return sosfilt(butter(2, [low, high], "band", fs=RATE, output="sos"), signal)


def saw(frequency: float, length: int) -> np.ndarray:
    phase = (np.arange(length) * frequency / RATE + rng.random()) % 1.0
    return 2 * phase - 1


def place(track: np.ndarray, sound: np.ndarray, start: float) -> None:
    begin = int(start * RATE)
    end = min(begin + len(sound), len(track))
    if begin < end:
        track[begin:end] += sound[: end - begin]


def pad_chord(notes: list[int], seconds: float, detune: float) -> np.ndarray:
    length = int(seconds * RATE)
    voice = sum(saw(hz(note) * 2 ** (cents / 1200), length) for note in notes for cents in (-detune, 0, detune))
    envelope = np.minimum(1, np.minimum(np.arange(length) / (0.25 * RATE), (length - np.arange(length)) / (0.25 * RATE)))
    return lowpass(voice * envelope, 900) / (len(notes) * 3)


def bass(note: int, seconds: float, decay: float = 0.18) -> np.ndarray:
    length = int(seconds * RATE)
    t = np.arange(length) / RATE
    tone = np.tanh(1.8 * np.sin(2 * np.pi * hz(note) * t))
    return lowpass(tone * np.exp(-t / decay) * np.minimum(1, t / 0.005), 600)


def kick() -> np.ndarray:
    t = np.arange(int(0.35 * RATE)) / RATE
    sweep = 45 + 85 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(sweep) / RATE) * np.exp(-t / 0.12)


def hat() -> np.ndarray:
    t = np.arange(int(0.05 * RATE)) / RATE
    return highpass(rng.standard_normal(len(t)), 7000) * np.exp(-t / 0.012)


def clap() -> np.ndarray:
    t = np.arange(int(0.2 * RATE)) / RATE
    return bandpass(rng.standard_normal(len(t)), 900, 4000) * np.exp(-t / 0.05)


def keys(note: int, seconds: float = 1.2, decay: float = 0.5) -> np.ndarray:
    length = int(seconds * RATE)
    t = np.arange(length) / RATE
    modulator = 1.2 * np.exp(-t / 0.25) * np.sin(2 * np.pi * hz(note) * 2 * t)
    tone = np.sin(2 * np.pi * hz(note) * t + modulator) + 0.25 * np.sin(2 * np.pi * hz(note) * 3 * t) * np.exp(-t / 0.15)
    return tone * np.exp(-t / decay) * np.minimum(1, t / 0.004)


def riser(seconds: float) -> np.ndarray:
    length = int(seconds * RATE)
    ramp = np.linspace(0, 1, length)
    noise = rng.standard_normal(length)
    return (lowpass(noise, 600) * (1 - ramp) + bandpass(noise, 1500, 6000) * ramp) * ramp**2


def crash() -> np.ndarray:
    t = np.arange(int(1.6 * RATE)) / RATE
    return bandpass(rng.standard_normal(len(t)), 3000, 9000) * np.exp(-t / 0.35)


def echo(signal: np.ndarray, delay: float, feedback: float, taps: int = 4) -> np.ndarray:
    out = signal.copy()
    offset = int(delay * RATE)
    for tap in range(1, taps + 1):
        out[offset * tap :] += signal[: len(signal) - offset * tap] * feedback**tap
    return out


def render(seconds: float, drop: float) -> np.ndarray:
    length = int(seconds * RATE)
    pad_left, pad_right, arp, low, drums = (np.zeros(length) for _ in range(5))
    duck = np.ones(length)

    intro_bars = int(np.ceil(drop / BAR))
    groove_from = 4
    build = min(5.0, drop)
    for bar in range(intro_bars):
        chord = PROGRESSION[(bar - intro_bars) % 4]
        start = drop - (intro_bars - bar) * BAR
        if start + BAR <= 0:
            continue
        place(pad_left, pad_chord(chord, BAR + 0.25, 9), start)
        place(pad_right, pad_chord(chord, BAR + 0.25, 13), start)
        tones = chord + [chord[0] + 12]
        for step, index in enumerate([0, 1, 2, 3, 2, 1, 2, 3]):
            place(arp, keys(tones[index] + 12) * (0.8 if step % 4 == 0 else 0.5), start + step * BEAT / 2)
        if bar < groove_from:
            place(low, bass(chord[0] - 12, BAR, 0.9) * 0.6, start)
            continue
        for beat in (0, 2):
            place(low, bass(chord[0] - 12, BEAT, 0.35) * 0.7, start + beat * BEAT)
        if start + BAR > drop - build / 2:
            continue
        for kick_at in (0, 1.5):
            place(drums, kick() * 0.8, start + kick_at * BEAT)
        place(drums, clap() * 0.3, start + 2 * BEAT)
        for eighth in range(8):
            place(drums, hat() * (0.18 if eighth % 2 else 0.1), start + eighth * BEAT / 2)

    place(drums, riser(build) * 0.22, drop - build)
    roll = drop - build
    while roll < drop - 1e-6:
        progress = 1 - (drop - roll) / build
        place(drums, clap() * (0.08 + 0.3 * progress), roll)
        roll += BEAT if progress < 0.4 else BEAT / 2 if progress < 0.75 else BEAT / 4

    bars = int(np.ceil((seconds - drop) / BAR))
    outro = bars - 3
    place(drums, crash() * 0.3, drop)
    for bar in range(bars):
        chord = PROGRESSION[0] if bar >= outro else PROGRESSION[bar % 4]
        start = drop + bar * BAR
        hold = (bars - bar) * BAR if bar == outro else BAR + 0.25
        if bar <= outro:
            place(pad_left, pad_chord(chord, hold, 9), start)
            place(pad_right, pad_chord(chord, hold, 13), start)
        if bar >= outro:
            continue

        pattern = [0, 1, 2, 1, 3, 2, 1, 2]
        tones = chord + [chord[0] + 12]
        for step in range(16):
            place(arp, keys(tones[pattern[step % 8]] + 12, 0.6, 0.18) * (0.8 if step % 4 == 0 else 0.5), start + step * BEAT / 4)

        if bar in (24, 25):
            continue

        for eighth in range(8):
            place(low, bass(chord[0] - 12, BEAT / 2), start + eighth * BEAT / 2)
        for beat in range(4):
            beat_start = start + beat * BEAT
            place(drums, kick(), beat_start)
            index = int(beat_start * RATE)
            window = np.arange(max(0, min(int(0.25 * RATE), length - index)))
            duck[index : index + len(window)] = np.minimum(duck[index : index + len(window)], 0.45 + 0.55 * (window / (0.25 * RATE)))
            place(drums, hat() * 0.35, beat_start + BEAT / 2)
            if bar >= 26:
                place(drums, hat() * 0.15, beat_start + BEAT / 4)
                place(drums, hat() * 0.15, beat_start + 3 * BEAT / 4)
            if beat in (1, 3):
                place(drums, clap() * 0.4, beat_start)

    arp = echo(lowpass(arp, 3000), BEAT * 0.75, 0.3)
    left = pad_left * 0.55 * duck + arp * 0.4 + low * 0.5 * duck + drums * 0.7
    right = pad_right * 0.55 * duck + echo(arp, BEAT * 0.5, 0.2) * 0.38 + low * 0.5 * duck + drums * 0.7
    stereo = np.stack([left, right], axis=1)
    lift = np.interp(np.arange(length) / RATE, [0, drop - build, drop], [0.7, 0.75, 1.0])
    fade = lift * np.clip((length - np.arange(length)) / (3 * RATE), 0, 1) * np.clip(np.arange(length) / (0.5 * RATE), 0, 1)
    stereo *= fade[:, None]
    stereo = np.tanh(stereo / np.abs(stereo).max() * 1.4) * 0.89
    return stereo


def write(path: str, stereo: np.ndarray) -> None:
    with wave.open(path, "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes((stereo * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    write(sys.argv[1], render(float(sys.argv[2]), float(sys.argv[3])))
