import { useState } from 'react'
import type { SaveData, Pokemon, ViewMode } from '../types/pokemon'
import { movePokemon } from '../api/client'
import { useViewMode } from '../hooks/useViewMode'
import { PartySidebar } from '../components/PartySidebar'
import { BoxPanel } from '../components/BoxPanel'
import { DetailPanel } from '../components/DetailPanel'
import styles from './MainView.module.css'

interface Props {
  save: SaveData
  onSaveUpdate: (s: SaveData) => void
}

interface DragState { box: number | string; slotNum: number; mon: Pokemon }

export function MainView({ save, onSaveUpdate }: Props) {
  const [activeBox, setActiveBox] = useState(0)
  const [selectedMon, setSelectedMon] = useState<Pokemon | null>(null)
  const [viewMode] = useViewMode('main-view-mode', 'grid')
  const [loading, setLoading] = useState(false)
  const [dragState, setDragState] = useState<DragState | null>(null)

  async function handleDrop(target: { box: number | string; slotNum: number }) {
    if (!dragState) return
    if (dragState.box === target.box && dragState.slotNum === target.slotNum) return
    setLoading(true)
    try {
      const updated = await movePokemon([{
        from: { box: dragState.box, slot: dragState.slotNum },
        to:   { box: target.box,   slot: target.slotNum },
      }])
      onSaveUpdate(updated)
      // Re-find selected mon
      if (selectedMon) {
        const all = [...updated.party.filter(Boolean), ...updated.boxes.flatMap(b => b.slots.map(s => s.mon).filter(Boolean))] as Pokemon[]
        setSelectedMon(all.find(m => m.pid === selectedMon.pid) ?? null)
      }
    } catch (err) {
      alert('Move failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
      setDragState(null)
    }
  }

  const boxes = save.boxes

  return (
    <div className={styles.layout}>
      <PartySidebar
        party={save.party}
        selectedPid={selectedMon?.pid}
        onSelect={setSelectedMon}
        onDragStart={setDragState}
        onDrop={handleDrop}
      />

      <div className={styles.boxArea}>
        {/* Tab bar */}
        <div className={styles.tabBar}>
          {boxes.map((box, idx) => {
            const isNamed = box.name && !box.name.match(/^Box \d+$/i) && box.name !== 'Preset'
            return (
              <button
                key={idx}
                className={`${styles.tab} ${isNamed ? styles.named : ''} ${activeBox === idx ? styles.active : ''}`}
                onClick={() => setActiveBox(idx)}
              >
                {box.name || `Box ${box.box}`}
              </button>
            )
          })}
        </div>

        {/* Active box */}
        {boxes[activeBox] && (
          <BoxPanel
            box={boxes[activeBox]}
            viewMode={viewMode as ViewMode}
            selectedPid={selectedMon?.pid}
            onSelect={setSelectedMon}
            onDragStart={setDragState}
            onDrop={handleDrop}
          />
        )}
      </div>

      <DetailPanel mon={selectedMon} />

      {loading && <div className={styles.loadingOverlay}>MOVING...</div>}
    </div>
  )
}
