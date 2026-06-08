import { useState } from 'react'
import type { Box, Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'

interface DragState { box: number | string; slotNum: number; mon: Pokemon }

interface Props {
  boxes: Box[]
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  onDragStart: (state: DragState) => void
  onDrop: (target: { box: number | string; slotNum: number }) => void
  multiSelected?: Set<number>
  selectColor?: 'move' | 'release'
  evoSet?: Set<number>
  shinyToggle?: boolean
}

export function CompactBoxView({ boxes, selectedPid, onSelect, onDragStart, onDrop, multiSelected, selectColor, evoSet, shinyToggle }: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

  function toggleCollapse(boxId: number) {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(boxId)) next.delete(boxId)
      else next.add(boxId)
      return next
    })
  }

  return (
    <div className="flex-1 overflow-auto p-2">
      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', alignItems: 'start' }}>
        {boxes.map(box => {
          const isCollapsed = collapsed.has(box.box)
          const monCount = box.slots.filter(s => s.mon).length
          return (
            <div key={box.box} className="bg-slate-900 border border-slate-700 rounded">
              <button
                className="w-full flex items-center gap-2 px-2 py-1 bg-slate-800 hover:bg-slate-750 border-b border-slate-700 transition-colors"
                onClick={() => toggleCollapse(box.box)}
              >
                <span className="text-[11px] font-semibold text-white flex-1 text-left truncate">
                  {box.name || `Box ${box.box}`}
                </span>
                <span className="text-[10px] text-slate-500">{monCount}/{box.slots.length}</span>
                <span className="text-[9px] text-slate-500 w-3">{isCollapsed ? '▶' : '▼'}</span>
              </button>
              {!isCollapsed && (
                <div className="grid gap-0.5 p-1" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
                  {box.slots.map((s, i) => {
                    if (s.split && !s.mon) return null
                    const slotNum = i + 1
                    const mon = s.mon
                    const isSelected = mon ? selectedPid === mon.pid : false
                    const isMulti = mon && multiSelected ? multiSelected.has(mon.pid) : false
                    const canEvo = mon && evoSet ? evoSet.has(mon.species) : false
                    const activeBg = isSelected
                      ? 'bg-blue-700 border-blue-400'
                      : isMulti
                        ? selectColor === 'release' ? 'bg-red-700 border-red-500' : 'bg-blue-700 border-blue-400'
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
                        style={{ height: '58px' }}
                        draggable={!!mon}
                        onClick={() => { if (mon) onSelect(mon) }}
                        onDragStart={() => { if (mon) onDragStart({ box: box.box, slotNum, mon }) }}
                        onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('ring-1', 'ring-blue-400') }}
                        onDragLeave={e => { e.currentTarget.classList.remove('ring-1', 'ring-blue-400') }}
                        onDrop={e => {
                          e.preventDefault()
                          e.currentTarget.classList.remove('ring-1', 'ring-blue-400')
                          onDrop({ box: box.box, slotNum })
                        }}
                      >
                        {mon && (
                          <>
                            {mon.shiny && (
                              <span className="absolute top-0 left-0.5 text-yellow-400 text-[8px] leading-none">★</span>
                            )}
                            {canEvo && (
                              <span className="absolute top-0 right-0.5 text-green-400 text-[8px] leading-none">▲</span>
                            )}
                            <Sprite speciesId={mon.species} shiny={mon.shiny} size={30} />
                            <span className="text-[8px] text-slate-300 leading-tight truncate w-full text-center px-0.5">
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
