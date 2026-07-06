// 0-100 mastery bar: red at 0 sweeping to green at 100 via the hue wheel.

interface MasteryBarProps {
  score: number
}

export default function MasteryBar({ score }: MasteryBarProps) {
  const clamped = Math.max(0, Math.min(100, score))
  const color = `hsl(${clamped * 1.2} 65% 42%)`
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-stone-200"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Mastery"
      >
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.max(clamped, 2)}%`, backgroundColor: color }}
        />
      </div>
      <span className="w-7 text-right text-xs font-semibold tabular-nums" style={{ color }}>
        {clamped}
      </span>
    </div>
  )
}
