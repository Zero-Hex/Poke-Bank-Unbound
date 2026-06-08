import type { Box, Pokemon, ViewMode } from '../types/pokemon'
import { PokemonBoxGrid } from './PokemonBoxGrid'
import { PokemonBoxList } from './PokemonBoxList'

interface DragSlot { box: number | string; slotNum: number; mon: Pokemon }
interface DropTarget { box: number | string; slotNum: number }

interface Props {
  box: Box
  viewMode: ViewMode
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  onDragStart?: (slot: DragSlot) => void
  onDrop?: (target: DropTarget) => void
  highlightPids?: Set<number>
  multiSelected?: Set<number>
  selectColor?: 'move' | 'release'
  extraControls?: React.ReactNode
  evoSet?: Set<number>
  shinyToggle?: boolean
}

export function BoxPanel({ box, viewMode, selectedPid, onSelect, onDragStart, onDrop, highlightPids, multiSelected, selectColor, extraControls, evoSet, shinyToggle }: Props) {
  const monCount = box.slots.filter(s => s.mon).length
  const cols = box.slots.length > 30 ? 7 : 6

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-slate-700 bg-slate-900 flex-none">
        <div className="text-sm font-semibold text-white flex-1">{box.name || `Box ${box.box}`}</div>
        <div className="text-xs text-slate-500">{monCount}/{box.slots.length}</div>
        {extraControls}
      </div>
      <div className="flex-1 overflow-auto">
        {viewMode === 'grid' ? (
          <PokemonBoxGrid
            slots={box.slots}
            cols={cols}
            boxId={box.box}
            selectedPid={selectedPid}
            onSelect={onSelect}
            onDragStart={onDragStart}
            onDrop={onDrop}
            highlightPids={highlightPids}
            multiSelected={multiSelected}
            selectColor={selectColor}
            evoSet={evoSet}
            shinyToggle={shinyToggle}
          />
        ) : (
          <PokemonBoxList
            slots={box.slots}
            boxId={box.box}
            selectedPid={selectedPid}
            onSelect={onSelect}
            onDragStart={onDragStart}
            onDrop={onDrop}
            highlightPids={highlightPids}
            multiSelected={multiSelected}
            shinyToggle={shinyToggle}
          />
        )}
      </div>
    </div>
  )
}
