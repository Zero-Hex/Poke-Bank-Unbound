import { useState } from 'react'
import type { VaultBox, Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'

type VaultSelectMode = 'off' | 'select' | 'release'

interface Props {
  vaultBoxes: VaultBox[]
  selectedVaultBox?: number | null
  selectedVaultSlot?: number | null
  onSelect: (mon: Pokemon, box: number, slot: number) => void
  onDragStart?: (src: { box: number; slot: number; mon: Pokemon }) => void
  onDrop?: (target: { box: number; slot: number }) => void
  multiSelectedPids?: Set<number>
  selectMode?: VaultSelectMode
  shinyToggle?: boolean
  isFiltering?: boolean
}

export function VaultCompactView({
  vaultBoxes, selectedVaultBox, selectedVaultSlot,
  onSelect, onDragStart, onDrop,
  multiSelectedPids, selectMode, shinyToggle, isFiltering,
}: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

  function toggleCollapse(boxId: number) {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(boxId)) next.delete(boxId)
      else next.add(boxId)
      return next
    })
  }

  const canDrag = !isFiltering

  return (
    <div className="flex-1 overflow-auto p-2">
      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', alignItems: 'start' }}>
        {vaultBoxes.map(box => {
          const isCollapsed = collapsed.has(box.box)
          const monCount = box.slots.filter(s => s.mon).length
          return (
            <div key={box.box} className="bg-slate-900 border border-slate-700 rounded">
              <button
                className="w-full flex items-center gap-2 px-2 py-1 bg-slate-800 border-b border-slate-700 transition-colors hover:bg-slate-750"
                onClick={() => toggleCollapse(box.box)}
              >
                <span className="text-[11px] font-semibold text-white flex-1 text-left truncate">{box.name}</span>
                <span className="text-[10px] text-slate-500">{monCount}/{box.slots.length}</span>
                <span className="text-[9px] text-slate-500 w-3">{isCollapsed ? '▶' : '▼'}</span>
              </button>
              {!isCollapsed && (
                <div className="grid gap-0.5 p-1" style={{ gridTemplateColumns: 'repeat(10, 1fr)' }}>
                  {box.slots.map((s, i) => {
                    const slotNum = i + 1
                    const mon = s.mon
                    const isSelected = selectedVaultBox === box.box && selectedVaultSlot === slotNum
                    const isMulti = mon && multiSelectedPids ? multiSelectedPids.has(mon.pid) : false
                    const activeBg = isSelected
                      ? 'bg-blue-700 border-blue-400'
                      : isMulti
                        ? selectMode === 'release' ? 'bg-red-700 border-red-500' : 'bg-blue-700 border-blue-400'
                        : mon ? 'bg-slate-800 border-slate-600' : 'bg-slate-900 border-slate-700'
                    const shinyClass = mon?.shiny && !isSelected && !isMulti && shinyToggle ? 'shiny-slot' : ''
                    return (
                      <div
                        key={i}
                        className={`
                          relative flex flex-col items-center justify-center rounded cursor-pointer select-none
                          border transition-colors overflow-hidden
                          ${mon ? 'hover:bg-slate-600' : 'opacity-25'}
                          ${activeBg} ${shinyClass}
                        `}
                        style={{ height: '50px' }}
                        draggable={!!mon && canDrag}
                        onClick={() => { if (mon) onSelect(mon, box.box, slotNum) }}
                        onDragStart={() => { if (mon && canDrag && onDragStart) onDragStart({ box: box.box, slot: slotNum, mon }) }}
                        onDragOver={e => { if (canDrag) { e.preventDefault(); e.currentTarget.classList.add('ring-1', 'ring-blue-400') } }}
                        onDragLeave={e => { e.currentTarget.classList.remove('ring-1', 'ring-blue-400') }}
                        onDrop={e => {
                          e.preventDefault()
                          e.currentTarget.classList.remove('ring-1', 'ring-blue-400')
                          if (canDrag && onDrop) onDrop({ box: box.box, slot: slotNum })
                        }}
                      >
                        {mon && (
                          <>
                            {mon.shiny && (
                              <span className="absolute top-0 left-0.5 text-yellow-400 text-[8px] leading-none">★</span>
                            )}
                            <Sprite speciesId={mon.species} shiny={mon.shiny} size={26} />
                            <span className="text-[7px] text-slate-300 leading-tight truncate w-full text-center px-0.5">
                              {mon.nick || mon.name}
                            </span>
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
