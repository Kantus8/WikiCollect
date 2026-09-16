import { useEffect } from "react";

export function Sound({ enabled }: { enabled: boolean }) {
  useEffect(() => {
    if (!enabled) return;
    try {
      const ctx = new AudioContext();
      [440, 554, 659].forEach((frequency, i) => {
        const oscillator = ctx.createOscillator(),
          gain = ctx.createGain();
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.035, ctx.currentTime + i * 0.09);
        gain.gain.exponentialRampToValueAtTime(
          0.001,
          ctx.currentTime + 0.5 + i * 0.09,
        );
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start(ctx.currentTime + i * 0.09);
        oscillator.stop(ctx.currentTime + 0.6 + i * 0.09);
      });
      const id = window.setTimeout(() => void ctx.close(), 1100);
      return () => {
        clearTimeout(id);
        void ctx.close();
      };
    } catch {
      /* Audio is optional. */
    }
  }, [enabled]);
  return null;
}
