import type { Box, Pokemon } from '../types/pokemon'
import { PokemonBoxGrid } from './PokemonBoxGrid'

interface DragSlot { box: number | string; slotNum: number; mon: Pokemon }
interface DropTarget { box: number | string; slotNum: number }

interface Props {
  box: Box
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  onDragStart?: (slot: DragSlot) => void
  onDrop?: (target: DropTarget) => void
  highlightPids?: Set<number>
  multiSelected?: Set<number>
}

export function BoxGrid({ box, selectedPid, onSelect, onDragStart, onDrop, highlightPids, multiSelected }: Props) {
  const cols = box.slots.length > 30 ? 7 : 6
  return (
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
    />
  )
}
