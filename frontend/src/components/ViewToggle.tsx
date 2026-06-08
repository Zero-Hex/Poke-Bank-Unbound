import type { ViewMode } from '../types/pokemon'

interface Props {
  mode: ViewMode
  onChange: (m: ViewMode) => void
}

export function ViewToggle({ mode, onChange }: Props) {
  return (
    <div className="flex rounded overflow-hidden border border-slate-600">
      <button
        className={`px-2 py-1 text-xs transition-colors ${mode === 'grid' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
        onClick={() => onChange('grid')}
        title="Grid view"
      >
        <GridIcon />
      </button>
      <button
        className={`px-2 py-1 text-xs transition-colors ${mode === 'list' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
        onClick={() => onChange('list')}
        title="List view"
      >
        <ListIcon />
      </button>
      <button
        className={`px-2 py-1 text-xs transition-colors ${mode === 'compact' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
        onClick={() => onChange('compact')}
        title="Compact view — all boxes at once"
      >
        <CompactIcon />
      </button>
    </div>
  )
}

function GridIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
      <rect x="0" y="0" width="6" height="6" rx="1"/>
      <rect x="8" y="0" width="6" height="6" rx="1"/>
      <rect x="0" y="8" width="6" height="6" rx="1"/>
      <rect x="8" y="8" width="6" height="6" rx="1"/>
    </svg>
  )
}

function ListIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
      <rect x="0" y="0" width="14" height="3" rx="1"/>
      <rect x="0" y="5" width="14" height="3" rx="1"/>
      <rect x="0" y="10" width="14" height="3" rx="1"/>
    </svg>
  )
}

function CompactIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
      <rect x="0" y="0" width="3" height="3" rx="0.5"/>
      <rect x="4" y="0" width="3" height="3" rx="0.5"/>
      <rect x="8" y="0" width="3" height="3" rx="0.5"/>
      <rect x="12" y="0" width="2" height="3" rx="0.5"/>
      <rect x="0" y="4" width="3" height="3" rx="0.5"/>
      <rect x="4" y="4" width="3" height="3" rx="0.5"/>
      <rect x="8" y="4" width="3" height="3" rx="0.5"/>
      <rect x="12" y="4" width="2" height="3" rx="0.5"/>
      <rect x="0" y="8" width="3" height="3" rx="0.5"/>
      <rect x="4" y="8" width="3" height="3" rx="0.5"/>
      <rect x="8" y="8" width="3" height="3" rx="0.5"/>
      <rect x="12" y="8" width="2" height="3" rx="0.5"/>
    </svg>
  )
}
