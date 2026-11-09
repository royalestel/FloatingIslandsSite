#!/usr/bin/env python3
"""MOCK MUSIC (python only, no VICE): runs Alpha.sid's init/play (NTSC: 5 play calls in 6 frames, as part 1 does) in the 6502
simulator (c64cpu), logs the SID registers after every call, and synthesises the tune to a WAV (3 voices, the four waveforms,
ADSR envelopes, pulse width; filter ignored).  Approximate: the real SID's filter and analogue quirks are not modelled.
    python3 mock_music_py.py SECONDS out.wav"""
import sys, wave, struct
import numpy as np
sys.path.insert(0, ".")
from c64cpu import MPU

def run_log(seconds):
    d = open("music/Alpha_ntsc.dat", "rb").read()
    m = MPU(); m.memory[0x1000:0x1000 + len(d)] = list(d)
    m.memory[0x0404] = 0xea
    def call(addr):
        m.memory[0x1fd] = 0x03; m.memory[0x1fe] = 0x04          # rts -> $0404
        m.sp = 0xfc; m.pc = addr; n = 0
        while m.pc != 0x0404 and n < 100000: m.step(); n += 1
    m.a = 0; call(0x1000)                                       # init (tune 0)
    calls = int(seconds * 50)                                   # 50 play calls a second
    log = np.zeros((calls, 25), dtype=np.uint8)
    for c in range(calls):
        call(0x1003)
        log[c] = [m.memory[0xd400 + r] for r in range(25)]
    return log

ADSR = {}  # attack, decay, release ms (SID table, rounded)
ATK = [2, 8, 16, 24, 38, 56, 68, 80, 100, 250, 500, 800, 1000, 3000, 5000, 8000]
DRL = [6, 24, 48, 72, 114, 168, 204, 240, 300, 750, 1500, 2400, 3000, 9000, 15000, 24000]

def synth(log, out, sr=44100):
    dt = 1.0 / 50; n_per = int(sr * dt)
    total = len(log) * n_per
    audio = np.zeros(total)
    phase = [0.0, 0.0, 0.0]; env = [0.0, 0.0, 0.0]; state = [0, 0, 0]   # state 0 idle,1 attack,2 decay,3 sustain,4 release
    rng = np.random.default_rng(1)
    for c in range(len(log)):
        r = log[c]
        seg = np.zeros(n_per)
        for v in range(3):
            b = 7 * v
            f = (int(r[b + 1]) << 8 | int(r[b])) * (985248 / 16777216) if False else (int(r[b + 1]) << 8 | int(r[b])) * (1022727 / 16777216)
            pw = ((int(r[b + 3]) & 0x0f) << 8 | int(r[b + 2])) / 4095.0
            ctrl = int(r[b + 4]); gate = ctrl & 1
            ad = int(r[b + 5]); sr_ = int(r[b + 6])
            atk, dec, sus, rel = ad >> 4, ad & 15, (sr_ >> 4) / 15.0, sr_ & 15
            if gate and state[v] in (0, 4): state[v] = 1
            if not gate and state[v] in (1, 2, 3): state[v] = 4
            step_t = dt / n_per
            e = np.zeros(n_per)
            for i in range(n_per):
                if state[v] == 1:
                    env[v] += step_t * 1000 / max(ATK[atk], 1) * 1.0
                    if env[v] >= 1: env[v] = 1; state[v] = 2
                elif state[v] == 2:
                    env[v] -= step_t * 1000 / max(DRL[dec], 1) * (1 - sus)
                    if env[v] <= sus: env[v] = sus; state[v] = 3
                elif state[v] == 4:
                    env[v] -= step_t * 1000 / max(DRL[rel], 1) * max(env[v], 0.01)
                    if env[v] <= 0.001: env[v] = 0; state[v] = 0
                e[i] = env[v]
            phase[v] += f * dt / n_per * 0 + 0
            ph = phase[v] + np.arange(n_per) * f / sr
            phase[v] = (phase[v] + n_per * f / sr) % 1.0
            x = ph % 1.0
            wave_ = np.zeros(n_per)
            if ctrl & 0x10: wave_ += np.where(x < 0.5, 4 * x - 1, 3 - 4 * x)           # triangle
            if ctrl & 0x20: wave_ += 2 * x - 1                                       # sawtooth
            if ctrl & 0x40: wave_ += np.where(x < pw, 1.0, -1.0)                     # pulse
            if ctrl & 0x80: wave_ += rng.uniform(-1, 1, n_per)                      # noise
            if ctrl & 0xf0: wave_ /= max(1, bin(ctrl >> 4).count("1")) ** 0.5
            seg += wave_ * e * 0.25
        vol = (int(r[24]) & 15) / 15.0
        audio[c * n_per:(c + 1) * n_per] = seg * vol
    audio = np.clip(audio * 0.7 * 32767, -32767, 32767).astype(np.int16)
    w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(audio.tobytes()); w.close()
    return out

if __name__ == "__main__":
    secs, out = float(sys.argv[1]), sys.argv[2]
    log = run_log(secs)
    np.save(out + ".regs.npy", log)
    print("logged", len(log), "play calls ->", synth(log, out))
