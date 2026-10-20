"""
GUNBOARD — every keypress is a gunshot.

  letters        -> pump shotgun   (each letter tuned slightly differently)
  numbers        -> 9mm pistol     (sharp, dry crack)
  special chars  -> sniper rifle   (crack + rolling echo)
  space          -> silenced pistol ("pfft")
  enter          -> shotgun pump reload (chk-chk)
  backspace      -> revolver dry-fire click
  tab            -> 3-round SMG burst
  caps lock      -> grenade
  F12            -> safety on/off (mute toggle)
  Ctrl+C in the terminal to quit
"""
import threading
import numpy as np
import sounddevice as sd
from pynput import keyboard

SR = 44100
MASTER = 0.6
rng = np.random.default_rng()


# ---------- synthesis helpers ----------
def t_axis(dur):
    return np.arange(int(SR * dur)) / SR

def env(dur, decay, attack=0.001):
    t = t_axis(dur)
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-t / decay)

def band_noise(dur, lo, hi):
    """White noise band-limited in the frequency domain (no scipy needed)."""
    n = int(SR * dur)
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    out = np.fft.irfft(spec, n)
    return out / (np.abs(out).max() + 1e-9)

def thump(dur, f0, f1, decay):
    """Sine whose pitch sweeps down f0 -> f1: the chest-hit of a gunshot."""
    t = t_axis(dur)
    freq = f1 + (f0 - f1) * np.exp(-t / 0.03)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * env(dur, decay)

def echo(x, delay, gain, taps=4):
    d = int(SR * delay)
    out = np.zeros(len(x) + d * taps)
    out[:len(x)] += x
    for k in range(1, taps + 1):
        out[k * d:k * d + len(x)] += x * gain ** k
    return out

def norm(x, peak=1.0):
    return peak * x / (np.abs(x).max() + 1e-9)

def silence(dur):
    return np.zeros(int(SR * dur))


# ---------- the arsenal ----------
def shotgun(tone=1.0):
    dur = 0.9
    boom = band_noise(dur, 40, 2500 * tone) * env(dur, 0.18)
    crack = band_noise(dur, 2000, 9000) * env(dur, 0.012)
    body = thump(dur, 160 * tone, 45, 0.15)
    return norm(0.9 * boom + 0.5 * crack + 1.0 * body)

def pistol():
    dur = 0.35
    crack = band_noise(dur, 1500, 12000) * env(dur, 0.02)
    body = band_noise(dur, 100, 1500) * env(dur, 0.06)
    return norm(crack + 0.6 * body + 0.5 * thump(dur, 300, 90, 0.04), 0.8)

def sniper():
    dur = 0.5
    crack = band_noise(dur, 3000, 14000) * env(dur, 0.008)
    boom = band_noise(dur, 50, 1200) * env(dur, 0.12)
    shot = crack + 0.8 * boom + thump(dur, 200, 50, 0.1)
    return norm(echo(shot, 0.18, 0.35, taps=5))

def silenced():
    dur = 0.18
    return norm(band_noise(dur, 300, 3000) * env(dur, 0.025), 0.45)

def click(f_lo, f_hi, dur=0.05, decay=0.006):
    return band_noise(dur, f_lo, f_hi) * env(dur, decay)

def pump_reload():
    back = click(800, 6000) + 0.3 * thump(0.05, 900, 600, 0.01)
    fwd = click(1200, 8000) + 0.3 * thump(0.05, 1100, 700, 0.01)
    return norm(np.concatenate([back, silence(0.09), fwd]), 0.7)

def dry_fire():
    return norm(np.concatenate([click(2000, 10000, 0.03, 0.003),
                                silence(0.02),
                                click(3000, 12000, 0.03, 0.002)]), 0.5)

def smg_burst():
    one = pistol()[: int(SR * 0.07)] * 0.9
    gap = silence(0.0)
    return norm(np.concatenate([one, gap, one, gap, one, pistol() * 0.9]))

def grenade():
    dur = 2.2
    boom = band_noise(dur, 20, 900) * env(dur, 0.45, attack=0.01)
    debris = band_noise(dur, 2000, 8000) * env(dur, 0.3) * 0.15
    return norm(boom + debris + 1.2 * thump(dur, 90, 25, 0.5))


print("Loading ammunition...")
LETTERS = {c: shotgun(0.75 + 0.5 * i / 25) for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
NUMBERS = [pistol() for _ in range(4)]      # a few variants so it doesn't sound robotic
SPECIAL = [sniper() for _ in range(3)]
SPECIAL_KEYS = {
    keyboard.Key.space: silenced(),
    keyboard.Key.enter: pump_reload(),
    keyboard.Key.backspace: dry_fire(),
    keyboard.Key.tab: smg_burst(),
    keyboard.Key.caps_lock: grenade(),
}


# ---------- mixer: lets shots overlap when you type fast ----------
voices = []          # list of [buffer, position]
lock = threading.Lock()
safety_on = False
MAX_VOICES = 16

def fire(buf):
    if safety_on:
        return
    gain = rng.uniform(0.85, 1.0)   # tiny variation per shot
    with lock:
        if len(voices) >= MAX_VOICES:
            voices.pop(0)
        voices.append([buf * gain, 0])

def callback(outdata, frames, time, status):
    mix = np.zeros(frames)
    with lock:
        for v in voices:
            buf, pos = v
            chunk = buf[pos:pos + frames]
            mix[:len(chunk)] += chunk
            v[1] += frames
        voices[:] = [v for v in voices if v[1] < len(v[0])]
    outdata[:, 0] = np.tanh(mix * MASTER)   # soft clip so stacked shots don't crackle


# ---------- keyboard ----------
def on_press(key):
    global safety_on
    if key == keyboard.Key.f12:
        safety_on = not safety_on
        print("SAFETY ON (muted)" if safety_on else "SAFETY OFF — weapons hot")
        return
    if key in SPECIAL_KEYS:
        fire(SPECIAL_KEYS[key])
        return
    ch = getattr(key, "char", None)
    if not ch:
        return                      # shift/ctrl/arrows etc. stay quiet
    c = ch.lower()
    if c in LETTERS:
        fire(LETTERS[c])
    elif c.isdigit():
        fire(NUMBERS[rng.integers(len(NUMBERS))])
    else:
        fire(SPECIAL[rng.integers(len(SPECIAL))])


if __name__ == "__main__":
    print(__doc__)
    with sd.OutputStream(samplerate=SR, channels=1, callback=callback, blocksize=256):
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
