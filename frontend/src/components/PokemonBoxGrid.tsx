import type { BoxSlot, Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'

interface Props {
  slots: BoxSlot[]
  cols?: number
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  onDragStart?: (slot: { box: number | string; slotNum: number; mon: Pokemon }) => void
  onDrop?: (target: { box: number | string; slotNum: number }) => void
  boxId: number | string
  highlightPids?: Set<number>
  multiSelected?: Set<number>
  selectColor?: 'move' | 'release'
  evoSet?: Set<number>
  shinyToggle?: boolean
}

export function PokemonBoxGrid({ slots, cols = 6, selectedPid, onSelect, onDragStart, onDrop, boxId, highlightPids, multiSelected, selectColor, evoSet, shinyToggle }: Props) {
  return (
    <div
      className="grid gap-0.5 p-1"
      style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
    >
      {slots.map((s, i) => {
        const slotNum = i + 1

        // Hide empty split slots (sector boundary — corrupt if you place a mon there)
        if (s.split && !s.mon) return null

        const mon = s.mon
        const isSelected = mon ? selectedPid === mon.pid : false
        const isHighlighted = mon && highlightPids ? highlightPids.has(mon.pid) : false
        const isMulti = mon && multiSelected ? multiSelected.has(mon.pid) : false
        const canEvo = mon && evoSet ? evoSet.has(mon.species) : false

        const activeBg = isSelected
          ? 'bg-blue-700 border-blue-400'
          : isMulti
            ? selectColor === 'release' ? 'bg-red-700 border-red-500' : 'bg-blue-700 border-blue-400'
            : isHighlighted
              ? 'bg-yellow-900 border-yellow-500'
              : mon ? 'bg-slate-800 border-slate-600' : 'bg-slate-900 border-slate-700'

        // Don't apply shiny animation when slot is visually selected — blue/red bg already signals selection
        const shinyClass = mon?.shiny && !isSelected && !isMulti && shinyToggle ? 'shiny-slot' : ''

        return (
          <div
            key={i}
            className={`
              relative flex flex-col items-center justify-center rounded cursor-pointer select-none
              border transition-colors min-h-[106px] p-0.5
              ${mon ? 'hover:bg-slate-600' : 'opacity-30'}
              ${activeBg} ${shinyClass}
            `}
            draggable={!!mon}
            data-box={boxId}
            data-slot={slotNum}
            onClick={() => { if (mon) onSelect(mon) }}
            onDragStart={() => { if (mon && onDragStart) onDragStart({ box: boxId, slotNum, mon }) }}
            onDragOver={e => { if (onDrop) { e.preventDefault(); e.currentTarget.classList.add('ring-2', 'ring-blue-400') } }}
            onDragLeave={e => { e.currentTarget.classList.remove('ring-2', 'ring-blue-400') }}
            onDrop={e => {
              e.preventDefault()
              e.currentTarget.classList.remove('ring-2', 'ring-blue-400')
              if (onDrop) onDrop({ box: boxId, slotNum })
            }}
          >
            {mon && (
              <>
                {mon.shiny && <span className="absolute top-0 left-0.5 text-yellow-400 text-[9px] leading-none z-10">★</span>}
                {canEvo && <span className="absolute top-0 right-0.5 text-[8px] font-bold text-purple-300 leading-none z-10">evo</span>}
                {s.split && <span className="absolute bottom-0 right-0.5 text-[8px] text-orange-400 leading-none z-10" title="Sector boundary — moving this Pokémon may corrupt the save">⚠</span>}
                <Sprite speciesId={mon.species} shiny={mon.shiny} size={80} />
                <span className="text-[9px] text-slate-300 leading-tight truncate w-full text-center">{mon.nick || mon.name}</span>
                <span className="text-[8px] text-slate-500">Lv.{mon.level}</span>
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}
