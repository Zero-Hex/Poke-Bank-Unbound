import type { Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'
import { TypeBadge } from './TypeBadge'

interface Props {
  party: (Pokemon | null)[]
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  onDragStart?: (slot: { box: number | string; slotNum: number; mon: Pokemon }) => void
  onDrop?: (target: { box: number | string; slotNum: number }) => void
  hasPortaPc?: boolean
  shinyToggle?: boolean
}

export function PartySidebar({ party, selectedPid, onSelect, onDragStart, onDrop, hasPortaPc = true, shinyToggle }: Props) {
  const partyTypes = new Set(
    party
      .filter(Boolean)
      .flatMap(mon => mon?.types ?? [])
  )

  return (
    <div className="w-48 flex-none flex flex-col bg-slate-900 border-r border-slate-700 overflow-y-auto">
      <div className="flex items-center gap-1 px-3 pt-3 pb-1">
        <span className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">Party</span>
        {!hasPortaPc && (
          <span className="text-[9px] text-amber-500 ml-auto" title="Earn the Porta-PC to move Pokémon between Party and PC">🔒 Porta-PC</span>
        )}
      </div>
      <div className="flex flex-col gap-1 p-2">
        {Array.from({ length: 6 }, (_, i) => {
          const mon = party[i] ?? null
          const isSelected = mon ? selectedPid === mon.pid : false
          return (
            <div
              key={i}
              className={`
                flex items-center gap-2 rounded px-2 py-1 border transition-colors cursor-pointer select-none
                ${mon ? 'hover:bg-slate-700' : 'opacity-40 cursor-default'}
                ${isSelected ? 'bg-blue-800 border-blue-500' : mon ? 'bg-slate-800 border-slate-700' : 'bg-slate-900 border-slate-800'}
                ${mon?.shiny && shinyToggle ? 'shiny-slot' : ''}
              `}
              draggable={!!mon && hasPortaPc}
              data-box="party"
              data-slot={i + 1}
              onClick={() => { if (mon) onSelect(mon) }}
              onDragStart={() => { if (mon && hasPortaPc && onDragStart) onDragStart({ box: 'party', slotNum: i + 1, mon }) }}
              onDragOver={e => { if (onDrop && hasPortaPc) { e.preventDefault(); e.currentTarget.classList.add('ring-2', 'ring-blue-400') } }}
              onDragLeave={e => { e.currentTarget.classList.remove('ring-2', 'ring-blue-400') }}
              onDrop={e => {
                e.preventDefault()
                e.currentTarget.classList.remove('ring-2', 'ring-blue-400')
                if (onDrop && hasPortaPc) onDrop({ box: 'party', slotNum: i + 1 })
              }}
            >
              {mon ? (
                <>
                  <Sprite speciesId={mon.species} shiny={mon.shiny} size={36} />
                  <div className="min-w-0">
                    <div className="text-xs text-white font-medium truncate">
                      {mon.shiny ? '★ ' : ''}{mon.nick || mon.name}
                    </div>
                    <div className="text-[10px] text-slate-400">Lv.{mon.level} · {mon.nature}</div>
                  </div>
                </>
              ) : (
                <span className="text-[10px] text-slate-600 uppercase tracking-wider">Empty</span>
              )}
            </div>
          )
        })}
      </div>

      {/* Type Coverage */}
      {partyTypes.size > 0 && (
        <div className="px-3 py-2 border-t border-slate-700 flex-none">
          <div className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-1">Type Coverage</div>
          <div className="flex flex-wrap gap-1">
            {Array.from(partyTypes).sort().map(type => (
              <TypeBadge key={type} type={type} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
