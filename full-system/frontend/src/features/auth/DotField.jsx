import { useEffect, useRef } from "react";

/**
 * Sign-in page background: a grid of small dots and plus signs.
 * Near the mouse they glide away and light up, then ease back into place.
 * Draws once (no movement) when the device asks for reduced motion.
 */
export default function DotField({ gap = 30, radius = 150 }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mouse = { x: -9999, y: -9999 };
    let points = [];
    let frame = 0;
    let w = 0;
    let h = 0;

    const build = () => {
      const dpr = window.devicePixelRatio || 1;
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      points = [];
      for (let y = gap / 2, row = 0; y < h; y += gap, row += 1) {
        for (let x = gap / 2 + (row % 2) * (gap / 2), col = 0; x < w; x += gap, col += 1) {
          points.push({ ox: x, oy: y, x, y, plus: (row * 7 + col * 3) % 5 === 0 });
        }
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of points) {
        const dx = p.ox - mouse.x;
        const dy = p.oy - mouse.y;
        const d = Math.hypot(dx, dy);
        const near = d < radius ? 1 - d / radius : 0;
        // push away from the cursor, then spring back to the home position
        const tx = p.ox + (d ? (dx / d) * near * 28 : 0);
        const ty = p.oy + (d ? (dy / d) * near * 28 : 0);
        p.x += (tx - p.x) * 0.12;
        p.y += (ty - p.y) * 0.12;
        const alpha = 0.18 + near * 0.75;
        ctx.strokeStyle = ctx.fillStyle = `rgba(${near > 0.05 ? "103,232,249" : "96,165,250"},${alpha})`;
        if (p.plus) {
          const s = 3.5 + near * 2;
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.moveTo(p.x - s, p.y);
          ctx.lineTo(p.x + s, p.y);
          ctx.moveTo(p.x, p.y - s);
          ctx.lineTo(p.x, p.y + s);
          ctx.stroke();
        } else {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 1.3 + near * 1.6, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      if (!still) frame = requestAnimationFrame(draw);
    };

    const move = (e) => {
      const r = canvas.getBoundingClientRect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
    };
    const leave = () => {
      mouse.x = -9999;
      mouse.y = -9999;
    };
    const resize = () => {
      build();
      if (still) draw();
    };

    build();
    draw();
    // refill the grid whenever the page grows or shrinks (not only on window resize)
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    window.addEventListener("pointermove", move);
    document.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
    };
  }, [gap, radius]);

  return <canvas ref={ref} className="absolute inset-0 h-full w-full" aria-hidden="true" />;
}

/** Slowly drifting colour glows behind a public page (sign-in, doctor sign-up), with dots that move away from the mouse. */
export function MovingBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="login-orb top-[-10%] left-[-5%] h-[28rem] w-[28rem] bg-brand-500/45" style={{ "--dx": "120px", "--dy": "80px", "--t": "20s" }} />
      <div className="login-orb right-[-8%] bottom-[-15%] h-[32rem] w-[32rem] bg-cyan-400/30" style={{ "--dx": "-140px", "--dy": "-60px", "--t": "26s" }} />
      <div className="login-orb top-[35%] left-[40%] h-[22rem] w-[22rem] bg-violet-500/30" style={{ "--dx": "-90px", "--dy": "110px", "--t": "30s" }} />
      <DotField />
    </div>
  );
}
