// Imperative visual effects (floating text + confetti burst). Framework-agnostic:
// appends throwaway DOM nodes to a fixed overlay so any component can trigger a
// celebration without wiring React state.

function layer(): HTMLElement {
  let el = document.getElementById("fx-layer");
  if (!el) {
    el = document.createElement("div");
    el.id = "fx-layer";
    document.body.appendChild(el);
  }
  return el;
}

/** A number/label that floats up and fades (e.g. "+15 XP"). */
export function floatText(text: string, color = "#f5b93b"): void {
  const el = document.createElement("div");
  el.className = "fx-float";
  el.textContent = text;
  el.style.color = color;
  el.style.left = 42 + Math.random() * 16 + "%";
  layer().appendChild(el);
  window.setTimeout(() => el.remove(), 1300);
}

const CONFETTI = ["#7c5cff", "#f5b93b", "#22d3a3", "#ff5d78", "#4f8dff", "#9d7bff"];

/** A celebratory confetti burst from the top-center. */
export function burst(pieces = 80): void {
  const host = layer();
  for (let i = 0; i < pieces; i++) {
    const p = document.createElement("div");
    p.className = "fx-confetti";
    p.style.background = CONFETTI[i % CONFETTI.length];
    p.style.left = 45 + Math.random() * 10 + "%";
    const dx = (Math.random() * 2 - 1) * 320;
    const dy = (Math.random() * -1 - 0.35) * 340;
    p.style.setProperty("--dx", dx + "px");
    p.style.setProperty("--dy", dy + "px");
    p.style.animationDelay = Math.random() * 0.12 + "s";
    host.appendChild(p);
    window.setTimeout(() => p.remove(), 1700);
  }
}
