// PlaybackBar — the /terminal scrub control (Session 39).
//
// Deliberately amber (risk-high token), never the neon-green "live" glow: the whole
// bar is a standing signal that the map is showing the PAST, not now. A native range
// input drives the scrub; RETURN TO LIVE (green) is always one click away so the
// operator can never get stranded in replay.
import type { Playback } from "@/features/terminal/usePlayback";

function fmt(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function PlaybackBar({ playback }: { playback: Playback }) {
  const { frames, index, playing, currentTs, loading, error, setIndex, togglePlay, exit } =
    playback;

  return (
    <div
      className="flex items-center gap-3 border-t-2 border-risk-high bg-risk-high/10 px-4 py-2"
      role="group"
      aria-label="Playback timeline"
    >
      <span className="shrink-0 text-2xs font-bold uppercase tracking-[0.18em] text-risk-high">
        ◀ Replay
      </span>

      <button
        type="button"
        onClick={togglePlay}
        disabled={loading || frames.length === 0}
        className="shrink-0 rounded border border-risk-high/40 px-2 py-0.5 text-2xs font-semibold uppercase text-risk-high hover:bg-risk-high/15 disabled:opacity-40"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? "❚❚ Pause" : "▶ Play"}
      </button>

      <input
        type="range"
        min={0}
        max={Math.max(frames.length - 1, 0)}
        value={index}
        onChange={(e) => setIndex(Number(e.target.value))}
        disabled={loading || frames.length === 0}
        aria-label="Scrub history"
        className="h-1 min-w-0 flex-1 cursor-pointer accent-risk-high"
      />

      <span
        className="shrink-0 font-mono text-2xs tabular-nums text-risk-high"
        aria-label="Replay timestamp"
      >
        {loading ? "loading history…" : error ? error : fmt(currentTs)}
      </span>

      <button
        type="button"
        onClick={exit}
        className="shrink-0 rounded border border-border-strong bg-risk-low/15 px-2.5 py-0.5 text-2xs font-bold uppercase tracking-wide text-risk-low hover:bg-risk-low/25"
      >
        ● Return to live
      </button>
    </div>
  );
}
