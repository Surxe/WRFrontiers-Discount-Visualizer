// Positions .wrf-tooltip__bubble above its icon and nudges it back inside the
// viewport near an edge. The .wrf-tooltip look/behaviour comes from the shared
// WRFrontiersDB-Design submodule (elements.css), which hosts CSS only - so this
// script is mirrored in each consumer. KEEP IN SYNC with the canonical copy in
// WRFrontiersDB-Design/README.md and WRFrontiers-Discount-Visualizer.
const MARGIN = 8;

function placeBubble(tip) {
  const bubble = tip.querySelector('.wrf-tooltip__bubble');
  if (!bubble) return;
  const icon = tip.getBoundingClientRect();
  bubble.style.setProperty('--tt-shift', '0px');
  bubble.style.left = `${icon.left + icon.width / 2}px`;
  bubble.style.top = `${icon.top}px`;
  const rect = bubble.getBoundingClientRect();
  let shift = 0;
  if (rect.right > window.innerWidth - MARGIN) {
    shift = -(rect.right - (window.innerWidth - MARGIN));
  } else if (rect.left < MARGIN) {
    shift = MARGIN - rect.left;
  }
  if (shift !== 0) bubble.style.setProperty('--tt-shift', `${shift}px`);
}

function handle(e) {
  const tip = e.target && e.target.closest && e.target.closest('.wrf-tooltip');
  if (tip) placeBubble(tip);
}

document.addEventListener('mouseover', handle);
document.addEventListener('focusin', handle);
