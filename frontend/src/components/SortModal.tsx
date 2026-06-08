import React from 'react'

interface Props {
  onClose: () => void
  onSort: (sortMode: string, scope: string, reserveBoxes: number) => void
}

type SortMode = 'evo_family' | 'level_asc' | 'level_desc' | 'species'
type Scope = 'all' | 'current'

const SORT_MODES: { value: SortMode; label: string }[] = [
  { value: 'evo_family', label: 'Evo Family' },
  { value: 'level_asc',  label: 'Level (Low → High)' },
  { value: 'level_desc', label: 'Level (High → Low)' },
  { value: 'species',    label: 'Species (Dex #)' },
]

export function SortModal({ onClose, onSort }: Props) {
  const [sortMode, setSortMode] = React.useState<SortMode>('evo_family')
  const [scope, setScope] = React.useState<Scope>('all')
  const [reserveBoxes, setReserveBoxes] = React.useState(0)

  function handleSort() {
    onSort(sortMode, scope, reserveBoxes)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-80 shadow-2xl">
        <h2 className="text-white font-bold text-lg mb-4">Sort PC Boxes</h2>

        <div className="mb-4">
          <div className="text-slate-400 text-xs uppercase tracking-wider mb-2">Sort By</div>
          {SORT_MODES.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 text-white text-sm py-1 cursor-pointer">
              <input
                type="radio"
                name="sortMode"
                value={value}
                checked={sortMode === value}
                onChange={() => setSortMode(value)}
                className="accent-blue-500"
              />
              {label}
            </label>
          ))}
        </div>

        <div className="mb-4">
          <div className="text-slate-400 text-xs uppercase tracking-wider mb-2">Scope</div>
          <label className="flex items-center gap-2 text-white text-sm py-1 cursor-pointer">
            <input type="radio" name="scope" value="all" checked={scope === 'all'} onChange={() => setScope('all')} className="accent-blue-500" />
            All Boxes
          </label>
          <label className="flex items-center gap-2 text-white text-sm py-1 cursor-pointer">
            <input type="radio" name="scope" value="current" checked={scope === 'current'} onChange={() => setScope('current')} className="accent-blue-500" />
            Current Box Only
          </label>
        </div>

        <div className="mb-6">
          <div className="text-slate-400 text-xs uppercase tracking-wider mb-2">Reserve Empty Boxes at End</div>
          <div className="flex gap-2">
            {[0, 1, 2].map(n => (
              <button
                key={n}
                className={`px-3 py-1 rounded text-sm font-semibold border transition-colors ${reserveBoxes === n ? 'bg-blue-600 border-blue-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
                onClick={() => setReserveBoxes(n)}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-2 justify-end">
          <button
            className="px-4 py-2 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 text-sm font-semibold transition-colors"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-500 text-sm font-semibold transition-colors"
            onClick={handleSort}
          >
            Sort
          </button>
        </div>
      </div>
    </div>
  )
}
