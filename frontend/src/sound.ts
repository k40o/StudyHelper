// Tiny synthesized sound effects via the Web Audio API — no asset files, works
// offline. Respects a persisted mute preference.

let ctx: AudioContext | null = null;
let muted =
  typeof localStorage !== "undefined" && localStorage.getItem("sh_muted") === "1";

function audio(): AudioContext | null {
  try {
    if (!ctx) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ctx = new AC();
    }
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function beep(freq: number, dur: number, type: OscillatorType = "sine", gain = 0.06, delay = 0) {
  const a = audio();
  if (!a) return;
  const osc = a.createOscillator();
  const g = a.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  osc.connect(g);
  g.connect(a.destination);
  const t = a.currentTime + delay;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(gain, t + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.start(t);
  osc.stop(t + dur + 0.03);
}

export const sound = {
  muted: () => muted,
  toggle(): boolean {
    muted = !muted;
    try {
      localStorage.setItem("sh_muted", muted ? "1" : "0");
    } catch {
      /* ignore */
    }
    if (!muted) beep(880, 0.08, "triangle", 0.05); // little confirmation blip
    return muted;
  },
  correct() {
    if (muted) return;
    beep(660, 0.1, "sine", 0.06);
    beep(990, 0.14, "sine", 0.05, 0.08);
  },
  wrong() {
    if (muted) return;
    beep(196, 0.22, "sawtooth", 0.05);
  },
  click() {
    if (muted) return;
    beep(520, 0.05, "triangle", 0.035);
  },
  levelUp() {
    if (muted) return;
    [523, 659, 784, 1047].forEach((f, i) => beep(f, 0.18, "triangle", 0.06, i * 0.09));
  },
  victory() {
    if (muted) return;
    [523, 659, 784, 1047, 1319].forEach((f, i) => beep(f, 0.2, "square", 0.045, i * 0.1));
  },
};
