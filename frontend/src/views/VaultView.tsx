import { useState, useEffect } from 'react'
import type { SaveData, Pokemon, VaultBox, ViewMode } from '../types/pokemon'
import {
  loadVault, vaultWithdraw, vaultSort, vaultBatchMove,
  vaultRename, speciesTypes, releasePokemon, undo, evoTable, baseStats, getPreferences,
} from '../api/client'
import { DetailPanel } from '../components/DetailPanel'
import { ViewToggle } from '../components/ViewToggle'
import { Sprite } from '../components/Sprite'
import { TypeBadge } from '../components/TypeBadge'
import { ListView } from '../components/ListView'
import { VaultCompactView } from '../components/VaultCompactView'

interface Props {
  save: SaveData
  onSaveUpdate: (s: SaveData) => void
}

interface SelectedVaultMon {
  mon: Pokemon
  vaultBox: number
  vaultSlot: number
}

type VaultSelectMode = 'off' | 'select' | 'release'

const VAULT_PAGE_SIZE = 10

function VaultBoxGrid({
  vaultBox,
  selectedVaultSlot,
  onSelect,
  multiSelectedPids,
  selectMode,
  onDragStart,
  onDrop,
  shinyToggle,
}: {
  vaultBox: VaultBox
  selectedVaultSlot?: number | null
  onSelect: (mon: Pokemon, slot: number) => void
  multiSelectedPids?: Set<number>
  selectMode?: VaultSelectMode
  onDragStart?: (src: { box: number; slot: number; mon: Pokemon }) => void
  onDrop?: (target: { box: number; slot: number }) => void
  shinyToggle?: boolean
}) {
  const cols = 15
  return (
    <div className="grid gap-0.5 p-1" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {vaultBox.slots.map((s, i) => {
        const mon = s.mon
        const slotNum = i + 1
        const isSingleSelected = selectedVaultSlot === slotNum
        const isMulti = mon && multiSelectedPids ? multiSelectedPids.has(mon.pid) : false

        const activeBg = isMulti
          ? (selectMode === 'release' ? 'bg-red-700 border-red-500' : 'bg-blue-700 border-blue-400')
          : isSingleSelected ? 'bg-blue-700 border-blue-400'
          : mon ? 'bg-slate-800 border-slate-600'
          : 'bg-slate-900 border-slate-700'

        const shinyClass = mon?.shiny && !isSingleSelected && !isMulti && shinyToggle ? 'shiny-slot' : ''

        return (
          <div
            key={i}
            className={`
              relative flex flex-col items-center justify-center rounded border transition-colors min-h-[52px] p-0.5 cursor-pointer
              ${mon ? 'hover:bg-slate-600' : 'opacity-25'}
              ${activeBg} ${shinyClass}
            `}
            draggable={!!mon && !!onDragStart}
            onClick={() => { if (mon) onSelect(mon, slotNum) }}
            onDragStart={() => { if (mon && onDragStart) onDragStart({ box: vaultBox.box, slot: slotNum, mon }) }}
            onDragOver={e => { if (onDrop) { e.preventDefault(); e.currentTarget.classList.add('ring-2', 'ring-blue-400') } }}
            onDragLeave={e => { e.currentTarget.classList.remove('ring-2', 'ring-blue-400') }}
            onDrop={e => {
              e.preventDefault()
              e.currentTarget.classList.remove('ring-2', 'ring-blue-400')
              if (onDrop) onDrop({ box: vaultBox.box, slot: slotNum })
            }}
          >
            {mon && (
              <>
                {mon.shiny && <span className="absolute top-0 left-0.5 text-yellow-400 text-[9px] leading-none">★</span>}
                <Sprite speciesId={mon.species} shiny={mon.shiny} size={36} />
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

export function VaultView({ save, onSaveUpdate }: Props) {
  const [vault, setVault] = useState<VaultBox[]>([])
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState('')
  const [selectedVaultMon, setSelectedVaultMon] = useState<SelectedVaultMon | null>(null)
  const [vaultPage, setVaultPage] = useState(0)
  const [activeVaultBox, setActiveVaultBox] = useState(0)
  const [showSortBar, setShowSortBar] = useState(false)
  const [sortMode, setSortMode] = useState<'national' | 'name' | 'level'>('national')
  const [renamingBox, setRenamingBox] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [specTypes, setSpecTypes] = useState<Record<string, string[]>>({})
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [shinyToggle, setShinyToggle] = useState(false)

  // Drag state
  const [vaultDragSrc, setVaultDragSrc] = useState<{ box: number; slot: number; mon: Pokemon } | null>(null)

  // Multi-select state
  const [vaultSelectMode, setVaultSelectMode] = useState<VaultSelectMode>('off')
  // Map from pid → {box, slot}
  const [multiVaultSelected, setMultiVaultSelected] = useState<Map<number, { box: number; slot: number }>>(new Map())
  const [showMoveVaultModal, setShowMoveVaultModal] = useState(false)
  const [showMovePCModal, setShowMovePCModal] = useState(false)

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [filterShiny, setFilterShiny] = useState(false)
  const [filterEvo, setFilterEvo] = useState<'off' | 'all' | 'missing'>('off')
  const [evoSet, setEvoSet] = useState<Set<number>>(new Set())
  const [evoFull, setEvoFull] = useState<Record<string, { target_id: number }[]>>({})
  const [baseStatsData, setBaseStatsData] = useState<Record<number, Record<string, number>>>({})

  useEffect(() => {
    loadVault().then(setVault).catch(() => {})
    speciesTypes().then(setSpecTypes).catch(() => {})
    evoTable().then(tbl => {
      setEvoSet(new Set(Object.keys(tbl).map(Number)))
      setEvoFull(tbl as unknown as Record<string, { target_id: number }[]>)
    }).catch(() => {})
    baseStats().then(setBaseStatsData).catch(() => {})
    getPreferences().then(p => setShinyToggle(p.shiny_toggle)).catch(() => {})
  }, [])

  function showFlash(msg: string) {
    setFlash(msg)
    setTimeout(() => setFlash(''), 3000)
  }

  async function withLoading<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setLoading(true)
    try { return await fn() }
    catch (err) { alert((err as Error).message) }
    finally { setLoading(false) }
  }

  function enrichMon(mon: Pokemon | null): Pokemon | null {
    if (!mon) return null
    const t = specTypes[String(mon.species)]
    return t ? { ...mon, types: t } : mon
  }

  function enterVaultMode(mode: 'select' | 'release') {
    setVaultSelectMode(mode)
    setMultiVaultSelected(new Map())
    setSelectedVaultMon(null)
  }

  function clearVaultMode() {
    setVaultSelectMode('off')
    setMultiVaultSelected(new Map())
  }

  function handleVaultMonClick(mon: Pokemon, vaultBox: number, vaultSlot: number) {
    if (vaultSelectMode !== 'off') {
      setMultiVaultSelected(prev => {
        const next = new Map(prev)
        if (next.has(mon.pid)) next.delete(mon.pid)
        else next.set(mon.pid, { box: vaultBox, slot: vaultSlot })
        return next
      })
    } else {
      setSelectedVaultMon({ mon, vaultBox, vaultSlot })
    }
  }

  async function handleVaultDrop(target: { box: number; slot: number }) {
    if (!vaultDragSrc) return
    if (vaultDragSrc.box === target.box && vaultDragSrc.slot === target.slot) {
      setVaultDragSrc(null)
      return
    }
    const src = vaultDragSrc
    setVaultDragSrc(null)
    const updated = await withLoading(() =>
      vaultBatchMove([{ from_box: src.box, from_slot: src.slot, to_box: target.box, to_slot: target.slot }])
    )
    if (updated) {
      setVault(updated)
      showFlash(`Moved ${src.mon.name}`)
    }
  }

  const searchLower = searchQuery.toLowerCase().trim()

  function monMatchesSearch(m: Pokemon): boolean {
    if (!searchLower) return true
    return (
      m.name.toLowerCase().includes(searchLower) ||
      (m.nick ? m.nick.toLowerCase().includes(searchLower) : false) ||
      m.nature.toLowerCase().includes(searchLower) ||
      m.ability.toLowerCase().includes(searchLower) ||
      (m.item ? m.item.toLowerCase().includes(searchLower) : false) ||
      (m.types?.some(t => t.toLowerCase().includes(searchLower)) ?? false) ||
      m.moves.some(mv => mv.toLowerCase().includes(searchLower)) ||
      (m.shiny && 'shiny'.includes(searchLower)) ||
      (m.gender ? m.gender.toLowerCase().includes(searchLower) : false) ||
      (evoSet.has(m.species) && ('evolve'.includes(searchLower) || 'can evolve'.includes(searchLower)))
    )
  }

  function monMatchesFilters(m: Pokemon): boolean {
    if (!monMatchesSearch(m)) return false
    if (filterShiny && !m.shiny) return false
    if (filterEvo === 'all' && !evoSet.has(m.species)) return false
    if (filterEvo === 'missing') {
      const hasEvo = evoSet.has(m.species) && m.level >= 50
      if (!hasEvo) return false
    }
    return true
  }

  const isFiltering = searchLower || filterShiny || filterEvo !== 'off'
  const filteredVault = isFiltering
    ? vault.map(vb => ({
        ...vb,
        slots: vb.slots.filter(slot => slot.mon && monMatchesFilters(slot.mon)),
      })).filter(vb => vb.slots.length > 0)
    : vault

  const vaultPageBoxes = isFiltering ? filteredVault : vault.slice(vaultPage * VAULT_PAGE_SIZE, (vaultPage + 1) * VAULT_PAGE_SIZE)
  const currentVaultBox = vaultPageBoxes[activeVaultBox]

  async function handleWithdraw() {
    if (!selectedVaultMon) return
    const updated = await withLoading(() =>
      vaultWithdraw(selectedVaultMon.vaultBox, selectedVaultMon.vaultSlot, 0, 0)
    )
    if (updated) {
      setVault(updated.vault)
      onSaveUpdate(updated.save)
      setSelectedVaultMon(null)
      showFlash(`Withdrew ${selectedVaultMon.mon.name} to PC`)
    }
  }

  async function handleUndo() {
    setLoading(true)
    try {
      const newSave = await undo()
      onSaveUpdate(newSave)
      const newVault = await loadVault()
      setVault(newVault)
      setSelectedVaultMon(null)
      setMultiVaultSelected(new Map())
      clearVaultMode()
      showFlash('Action undone')
    }
    catch (err) { alert('Undo failed: ' + (err as Error).message) }
    finally { setLoading(false) }
  }

  async function handleSingleRelease() {
    if (!selectedVaultMon) return
    if (!confirm(`Release ${selectedVaultMon.mon.name} from vault? This cannot be undone.`)) return
    setLoading(true)
    try {
      const result = await releasePokemon([{ box: selectedVaultMon.vaultBox, slot: selectedVaultMon.vaultSlot, vault: true }])
      onSaveUpdate(result)
      const newVault = await loadVault()
      setVault(newVault)
      setSelectedVaultMon(null)
      showFlash(`Released ${selectedVaultMon.mon.name}`)
    } catch (err) {
      alert('Release failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMultiRelease() {
    if (multiVaultSelected.size === 0) return
    const items = Array.from(multiVaultSelected.entries()).map(([, loc]) => ({
      box: loc.box, slot: loc.slot, vault: true as const,
    }))
    const names = Array.from(multiVaultSelected.keys())
      .map(pid => {
        for (const vb of vault) {
          for (const s of vb.slots) {
            if (s.mon?.pid === pid) return s.mon.name
          }
        }
        return '?'
      })
      .join(', ')
    if (!confirm(`Release ${items.length} Pokémon from vault?\n${names}\n\nThis cannot be undone.`)) return
    setLoading(true)
    try {
      const result = await releasePokemon(items)
      onSaveUpdate(result)
      const newVault = await loadVault()
      setVault(newVault)
      clearVaultMode()
      showFlash(`Released ${items.length} Pokémon`)
    } catch (err) {
      alert('Release failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMoveToVaultBox(targetBoxNum: number) {
    setShowMoveVaultModal(false)
    const selectedItems = Array.from(multiVaultSelected.entries())
    const itemsToMove = selectedItems.filter(([, loc]) => loc.box !== targetBoxNum)
    if (itemsToMove.length === 0) { clearVaultMode(); return }

    const targetBox = vault.find(b => b.box === targetBoxNum)
    if (!targetBox) return
    // Claim empty slots in target box (not occupied by selected mons being moved there)
    const emptySlots = targetBox.slots
      .map((s, i) => ({ slotNum: i + 1, empty: !s.mon }))
      .filter(x => x.empty)
      .map(x => x.slotNum)

    if (emptySlots.length < itemsToMove.length) {
      alert(`Not enough space in that vault box (need ${itemsToMove.length}, have ${emptySlots.length} free slots)`)
      return
    }

    setLoading(true)
    try {
      const moves = itemsToMove.map(([, loc], i) => ({
        from_box: loc.box,
        from_slot: loc.slot,
        to_box: targetBoxNum,
        to_slot: emptySlots[i],
      }))
      const updatedVault = await vaultBatchMove(moves)
      setVault(updatedVault)
      clearVaultMode()
      showFlash(`Moved ${itemsToMove.length} Pokémon to ${targetBox.name || `Vault Box ${targetBoxNum}`}`)
    } catch (err) {
      alert('Move failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMoveToPC(targetBoxNum: number) {
    setShowMovePCModal(false)
    const selectedItems = Array.from(multiVaultSelected.entries())
    const pcBox = save.boxes.find(b => b.box === targetBoxNum)
    if (!pcBox) return
    const emptySlots = pcBox.slots
      .map((s, i) => ({ slotNum: i + 1, usable: !s.split && !s.mon }))
      .filter(x => x.usable)
      .map(x => x.slotNum)
    if (emptySlots.length < selectedItems.length) {
      alert(`Not enough space in that PC box (need ${selectedItems.length}, have ${emptySlots.length} free slots)`)
      return
    }
    setLoading(true)
    try {
      let lastSave = save
      let updatedVault = vault
      for (let i = 0; i < selectedItems.length; i++) {
        const [, loc] = selectedItems[i]
        const result = await vaultWithdraw(loc.box, loc.slot, targetBoxNum, emptySlots[i])
        lastSave = result.save
        updatedVault = result.vault
      }
      onSaveUpdate(lastSave)
      setVault(updatedVault)
      clearVaultMode()
      showFlash(`Moved ${selectedItems.length} Pokémon to PC Box ${targetBoxNum}`)
    } catch (err) {
      alert('Move to PC failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleVaultSort(scope: 'all' | 'box') {
    const box = scope === 'box' ? currentVaultBox?.box : undefined
    const updated = await withLoading(() => vaultSort(sortMode, scope, box))
    if (updated) {
      setVault(updated)
      showFlash(`Sorted ${scope === 'all' ? 'all vault boxes' : 'current box'}`)
    }
  }

  async function submitRename() {
    if (renamingBox === null) return
    const updated = await withLoading(() =>
      vaultRename(renamingBox, renameValue.trim() || `Vault ${renamingBox}`)
    )
    if (updated) setVault(updated)
    setRenamingBox(null)
  }

  const multiVaultPids = new Set(multiVaultSelected.keys())
  const selectedMonEnriched = selectedVaultMon ? enrichMon(selectedVaultMon.mon) : null

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">

        {/* Multi-select floating banner */}
        {vaultSelectMode !== 'off' && (
          <div className="flex items-center gap-3 px-4 py-2 bg-amber-950 border-b border-amber-800 flex-none">
            {vaultSelectMode === 'select' ? (
              <>
                <span className="text-amber-200 text-xs font-medium flex-1">
                  {multiVaultSelected.size === 0
                    ? 'Click Pokémon to select — Move to PC or Vault Box'
                    : `${multiVaultSelected.size} selected`}
                </span>
                <button
                  className="px-3 py-1 rounded text-xs font-semibold bg-blue-700 border border-blue-500 text-white hover:bg-blue-600 transition-colors disabled:opacity-40"
                  onClick={() => setShowMovePCModal(true)}
                  disabled={multiVaultSelected.size === 0}
                >
                  Move {multiVaultSelected.size > 0 ? multiVaultSelected.size : ''} to PC Box
                </button>
                <button
                  className="px-3 py-1 rounded text-xs font-semibold bg-purple-700 border border-purple-500 text-white hover:bg-purple-600 transition-colors disabled:opacity-40"
                  onClick={() => setShowMoveVaultModal(true)}
                  disabled={multiVaultSelected.size === 0}
                >
                  Move {multiVaultSelected.size > 0 ? multiVaultSelected.size : ''} to Vault Box
                </button>
              </>
            ) : (
              <>
                <span className="text-amber-200 text-xs font-medium flex-1">
                  {multiVaultSelected.size === 0
                    ? 'Click Pokémon to select for release'
                    : `${multiVaultSelected.size} selected for release — click more or confirm`}
                </span>
                <button
                  className="px-3 py-1 rounded text-xs font-semibold bg-red-700 border border-red-600 text-white hover:bg-red-600 transition-colors disabled:opacity-40"
                  onClick={handleMultiRelease}
                  disabled={multiVaultSelected.size === 0}
                >
                  Release {multiVaultSelected.size > 0 ? `${multiVaultSelected.size} Pokémon` : ''}
                </button>
              </>
            )}
            <button className="text-amber-400 hover:text-white text-lg leading-none px-1" onClick={clearVaultMode} title="Cancel">×</button>
          </div>
        )}

        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-700 bg-slate-900 flex-none">
          <span className="text-white font-bold text-sm">Vault</span>
          <div className="flex-1" />
          {flash && <span className="text-emerald-400 text-xs">{flash}</span>}
          <ViewToggle mode={viewMode} onChange={setViewMode} />
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${vaultSelectMode === 'select' ? 'bg-blue-700 border-blue-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => vaultSelectMode === 'select' ? clearVaultMode() : enterVaultMode('select')}
          >
            Multi-Move
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${vaultSelectMode === 'release' ? 'bg-red-800 border-red-600 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => vaultSelectMode === 'release' ? clearVaultMode() : enterVaultMode('release')}
          >
            Release
          </button>
          {vaultSelectMode !== 'off' && (
            <>
              <button
                className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
                onClick={() => {
                  const allPids = new Map<number, { box: number; slot: number }>()
                  vault.forEach(vb => {
                    vb.slots.forEach((vs, idx) => {
                      if (vs.mon) {
                        allPids.set(vs.mon.pid, { box: vb.box, slot: idx + 1 })
                      }
                    })
                  })
                  setMultiVaultSelected(allPids)
                }}
                title="Select all Pokémon"
              >
                Select All
              </button>
              <button
                className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
                onClick={() => setMultiVaultSelected(new Map())}
                title="Deselect all Pokémon"
              >
                Deselect All
              </button>
            </>
          )}
          <div className="w-px h-4 bg-slate-600 mx-0.5" />
          <button
            className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleUndo}
            disabled={loading}
            title="Undo last action"
          >
            Undo
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${showSortBar ? 'bg-blue-700 border-blue-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setShowSortBar(s => !s)}
          >
            Sort
          </button>
        </div>

        {/* Search and filter toolbar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-700 bg-slate-900/50 flex-none">
          <input
            type="text"
            placeholder="Search name, nature, ability, item, type, move..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="px-2 py-1 rounded text-xs bg-slate-800 border border-slate-700 text-white placeholder-slate-500 flex-1"
          />
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${filterShiny ? 'bg-yellow-500 border-yellow-400 text-slate-900' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setFilterShiny(!filterShiny)}
            title="Filter by shiny"
          >
            ★ Shiny
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${filterEvo === 'all' ? 'bg-purple-700 border-purple-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setFilterEvo(filterEvo === 'all' ? 'off' : 'all')}
            title="Filter by can evolve"
          >
            Can Evolve
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${filterEvo === 'missing' ? 'bg-orange-600 border-orange-400 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setFilterEvo(filterEvo === 'missing' ? 'off' : 'missing')}
            title="Filter by missing evolution"
          >
            Missing Evo
          </button>
          {isFiltering && (
            <button
              className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
              onClick={() => { setSearchQuery(''); setFilterShiny(false); setFilterEvo('off') }}
              title="Clear filters"
            >
              Clear Filters
            </button>
          )}
        </div>

        {/* Filter results indicator */}
        {isFiltering && (
          <div className="px-4 py-1.5 text-xs text-slate-400 border-b border-slate-700 bg-slate-900/30 flex-none flex items-center gap-2">
            <span>Showing {filteredVault.reduce((sum, vb) => sum + vb.slots.length, 0)} results</span>
            {searchLower && <span className="text-slate-500">for "{searchQuery}"</span>}
            {filterShiny && <span className="text-yellow-400">★ Shiny</span>}
            {filterEvo === 'all' && <span className="text-purple-400">Can Evolve</span>}
            {filterEvo === 'missing' && <span className="text-orange-400">Missing Evo</span>}
          </div>
        )}

        {/* Sort toolbar */}
        {showSortBar && (
          <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 border-b border-slate-700 flex-none">
            <span className="text-xs text-slate-400">Sort by:</span>
            {(['national', 'name', 'level'] as const).map(mode => (
              <button
                key={mode}
                className={`px-2 py-0.5 rounded text-xs font-medium border transition-colors ${sortMode === mode ? 'bg-blue-600 border-blue-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
                onClick={() => setSortMode(mode)}
              >
                {mode === 'national' ? 'Dex #' : mode === 'name' ? 'Name' : 'Level'}
              </button>
            ))}
            <div className="w-px h-4 bg-slate-600 mx-1" />
            <button
              className="px-2 py-0.5 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
              onClick={() => handleVaultSort('box')}
            >
              Sort This Page
            </button>
            <button
              className="px-2 py-0.5 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
              onClick={() => handleVaultSort('all')}
            >
              Sort All Boxes
            </button>
          </div>
        )}

        {/* Single-select action bar — hidden when multi-select mode is active */}
        {selectedVaultMon && vaultSelectMode === 'off' && (
          <div className="flex items-center gap-2 px-4 py-1.5 bg-blue-900/30 border-b border-blue-800 flex-none">
            <div className="flex items-center gap-1.5">
              <Sprite speciesId={selectedVaultMon.mon.species} size={28} />
              <span className="text-white text-xs font-medium">{selectedVaultMon.mon.name}</span>
              {selectedVaultMon.mon.types?.map(t => <TypeBadge key={t} type={t} />)}
            </div>
            <div className="flex-1" />
            <button
              className="px-2 py-1 rounded text-xs bg-green-700 border border-green-600 text-white hover:bg-green-600 transition-colors"
              onClick={handleWithdraw}
            >
              Withdraw to PC
            </button>
            <button
              className="px-2 py-1 rounded text-xs bg-red-700 border border-red-600 text-white hover:bg-red-600 transition-colors"
              onClick={handleSingleRelease}
            >
              Release
            </button>
            <button
              className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
              onClick={() => setSelectedVaultMon(null)}
            >
              Deselect
            </button>
          </div>
        )}

        {/* Page tabs — hidden in list/compact mode (they show all boxes) */}
        {viewMode === 'grid' && (
          <div className="flex gap-0 border-b border-slate-700 bg-slate-900 flex-none">
            {[
              { label: 'Page 1 (1–10)', page: 0 },
              { label: 'Page 2 (11–20)', page: 1 },
              { label: 'Page 3 (21–30)', page: 2 },
            ].map(({ label, page }) => (
              <button
                key={page}
                className={`px-4 py-1.5 text-xs font-medium border-r border-slate-700 transition-colors
                  ${vaultPage === page ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800'}
                `}
                onClick={() => { setVaultPage(page); setActiveVaultBox(0) }}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Rename input */}
        {renamingBox !== null && (
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-slate-700 bg-slate-800 flex-none">
            <span className="text-xs text-slate-400">Rename:</span>
            <input
              className="bg-slate-700 border border-slate-500 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-blue-400 w-40"
              value={renameValue}
              onChange={e => setRenameValue(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') submitRename(); if (e.key === 'Escape') setRenamingBox(null) }}
              autoFocus
              maxLength={20}
            />
            <button className="px-2 py-0.5 rounded text-xs bg-blue-700 text-white hover:bg-blue-600" onClick={submitRename}>Save</button>
            <button className="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-300 hover:bg-slate-600" onClick={() => setRenamingBox(null)}>Cancel</button>
          </div>
        )}

        {/* Vault boxes — grid, list, or compact */}
        <div className="flex-1 overflow-auto flex flex-col min-h-0">
          {vault.length === 0 && (
            <div className="text-slate-500 text-sm p-8 text-center">No vault boxes loaded</div>
          )}
          {viewMode === 'compact' ? (
            <VaultCompactView
              vaultBoxes={isFiltering ? filteredVault : vault}
              selectedVaultBox={selectedVaultMon?.vaultBox}
              selectedVaultSlot={selectedVaultMon?.vaultSlot}
              onSelect={handleVaultMonClick}
              onDragStart={!isFiltering ? setVaultDragSrc : undefined}
              onDrop={!isFiltering ? handleVaultDrop : undefined}
              multiSelectedPids={vaultSelectMode !== 'off' ? multiVaultPids : undefined}
              selectMode={vaultSelectMode}
              shinyToggle={shinyToggle}
              isFiltering={!!isFiltering}
            />
          ) : viewMode === 'list' ? (
            <ListView
              boxes={
                (isFiltering ? filteredVault : vault)
                  .map(vb => ({ box: vb.box, name: vb.name, slots: vb.slots.map(s => ({ mon: s.mon })) }))
              }
              selectedPid={selectedVaultMon?.mon.pid}
              onSelect={(mon) => {
                const allBoxes = isFiltering ? filteredVault : vault
                const vaultMon = allBoxes
                  .flatMap(b => b.slots.map((s, i) => ({ mon: s.mon, box: b.box, slot: i + 1 })))
                  .find(x => x.mon?.pid === mon.pid)
                if (vaultMon?.mon && vaultMon.box) {
                  handleVaultMonClick(vaultMon.mon, vaultMon.box, vaultMon.slot)
                }
              }}
              multiSelected={vaultSelectMode !== 'off' ? multiVaultPids : undefined}
              selectColor={vaultSelectMode === 'release' ? 'release' : 'move'}
            />
          ) : (
            vaultPageBoxes.map((box, idx) => {
              const count = box.slots.filter(s => s.mon).length
              return (
                <div key={box.box} className="border-b border-slate-800">
                  <div className="flex items-center gap-2 px-3 py-1 bg-slate-900/60">
                    <span className="text-xs font-semibold text-slate-300">{idx + 1 + vaultPage * VAULT_PAGE_SIZE}</span>
                    <span
                      className="text-xs text-white font-medium cursor-pointer hover:text-blue-300"
                      title="Click to rename"
                      onClick={() => { setRenamingBox(box.box); setRenameValue(box.name) }}
                    >
                      {box.name}
                    </span>
                    <span className="text-[10px] text-slate-500 ml-auto">{count}/{box.slots.length}</span>
                  </div>
                  <VaultBoxGrid
                    vaultBox={box}
                    selectedVaultSlot={selectedVaultMon?.vaultBox === box.box ? selectedVaultMon.vaultSlot : null}
                    onSelect={(mon, slot) => handleVaultMonClick(mon, box.box, slot)}
                    multiSelectedPids={vaultSelectMode !== 'off' ? multiVaultPids : undefined}
                    selectMode={vaultSelectMode}
                    onDragStart={!isFiltering ? setVaultDragSrc : undefined}
                    onDrop={!isFiltering ? handleVaultDrop : undefined}
                    shinyToggle={shinyToggle}
                  />
                </div>
              )
            })
          )}
        </div>
      </div>

      <DetailPanel mon={selectedMonEnriched} evoFull={evoFull} baseStatsData={baseStatsData} />

      {/* Move to PC Box modal */}
      {showMovePCModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowMovePCModal(false)}>
          <div className="bg-slate-800 rounded-lg p-4 w-80 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="text-white font-semibold text-sm mb-1">Move {multiVaultSelected.size} Pokémon to PC box:</div>
            <div className="text-slate-500 text-[10px] mb-2">Grayed boxes don't have enough free slots</div>
            <div className="overflow-auto flex-1">
              {save.boxes.map(box => {
                const free = box.slots.filter(s => !s.split && !s.mon).length
                const enough = free >= multiVaultSelected.size
                return (
                  <button
                    key={box.box}
                    disabled={!enough}
                    className={`w-full flex items-center justify-between px-3 py-1.5 text-xs rounded transition-colors mb-0.5
                      ${enough ? 'text-slate-300 hover:bg-slate-700 hover:text-white cursor-pointer' : 'text-slate-600 cursor-not-allowed'}
                    `}
                    onClick={() => enough && handleMoveToPC(box.box as number)}
                  >
                    <span>{box.name || `Box ${box.box}`}</span>
                    <span className={`text-[10px] ${enough ? 'text-emerald-400' : 'text-slate-600'}`}>{free} free</span>
                  </button>
                )
              })}
            </div>
            <button className="mt-3 px-3 py-1 text-xs bg-slate-600 hover:bg-slate-500 text-white rounded" onClick={() => setShowMovePCModal(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Move to Vault Box modal */}
      {showMoveVaultModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowMoveVaultModal(false)}>
          <div className="bg-slate-800 rounded-lg p-4 w-80 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="text-white font-semibold text-sm mb-1">Move {multiVaultSelected.size} Pokémon to vault box:</div>
            <div className="text-slate-500 text-[10px] mb-2">Grayed boxes don't have enough free slots</div>
            <div className="overflow-auto flex-1">
              {vault.map(vb => {
                const free = vb.slots.filter(s => !s.mon).length
                // How many items are already in this box (they won't need a new slot)
                const alreadyHere = Array.from(multiVaultSelected.values()).filter(loc => loc.box === vb.box).length
                const needed = multiVaultSelected.size - alreadyHere
                const enough = free >= needed
                return (
                  <button
                    key={vb.box}
                    disabled={!enough}
                    className={`w-full flex items-center justify-between px-3 py-1.5 text-xs rounded transition-colors mb-0.5
                      ${enough ? 'text-slate-300 hover:bg-slate-700 hover:text-white cursor-pointer' : 'text-slate-600 cursor-not-allowed'}
                    `}
                    onClick={() => enough && handleMoveToVaultBox(vb.box)}
                  >
                    <span>{vb.name || `Vault Box ${vb.box}`}</span>
                    <span className={`text-[10px] ${enough ? 'text-emerald-400' : 'text-slate-600'}`}>{free} free</span>
                  </button>
                )
              })}
            </div>
            <button className="mt-3 px-3 py-1 text-xs bg-slate-600 hover:bg-slate-500 text-white rounded" onClick={() => setShowMoveVaultModal(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 pointer-events-none">
          <div className="bg-slate-800 px-6 py-3 rounded-lg text-white text-sm font-semibold">LOADING...</div>
        </div>
      )}
    </div>
  )
}
