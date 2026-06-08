import { useState, useEffect, useMemo } from 'react'
import type { SaveData, Pokemon, ViewMode, VaultBox } from '../types/pokemon'
import { movePokemon, sortPC, releasePokemon, speciesTypes, evoTable, exportExcel, exportEvolutions, moveToBox, vaultBatchDeposit, loadVault, dexFlags, speciesToNational, undo, getPreferences, setPreferences, baseStats } from '../api/client'
import { useViewMode } from '../hooks/useViewMode'
import { PartySidebar } from '../components/PartySidebar'
import { BoxPanel } from '../components/BoxPanel'
import { DetailPanel } from '../components/DetailPanel'
import { SortModal } from '../components/SortModal'
import { ListView } from '../components/ListView'
import { ViewToggle } from '../components/ViewToggle'
import { IVEVCalculator } from '../components/IVEVCalculator'
import { CompactBoxView } from '../components/CompactBoxView'

interface Props {
  save: SaveData
  onSaveUpdate: (s: SaveData) => void
  hasPortaPc: boolean
}

interface DragState { box: number | string; slotNum: number; mon: Pokemon }

const TABS = [
  { label: '1–10',  filter: (b: { box: number }) => b.box >= 1 && b.box <= 10 },
  { label: '11–20', filter: (b: { box: number }) => b.box >= 11 && b.box <= 20 },
  { label: '21–24', filter: (b: { box: number }) => b.box >= 21 && b.box <= 24 },
]

const STAT_ORDER = ['hp','atk','def','spa','spd','spe'] as const
const STAT_LABELS: Record<string,string> = { hp:'HP', atk:'Atk', def:'Def', spa:'SpA', spd:'SpD', spe:'Spe' }

// Format per https://pokepast.es/syntax.html
function makePaste(mons: Pokemon[]): string {
  return mons.map(m => {
    const hasNick = m.nick && m.nick !== m.name
    const header = hasNick
      ? `${m.nick} (${m.name})${m.item ? ` @ ${m.item}` : ''}`
      : `${m.name}${m.item ? ` @ ${m.item}` : ''}`
    const gender = m.gender === 'M' ? '\nGender: Male' : m.gender === 'F' ? '\nGender: Female' : ''
    const ability = `\nAbility: ${m.ability}`
    const level = m.level !== 100 ? `\nLevel: ${m.level}` : ''
    const shiny = m.shiny ? '\nShiny: Yes' : ''
    const ivLines = STAT_ORDER.filter(s => m.ivs[s] < 31).map(s => `${m.ivs[s]} ${STAT_LABELS[s]}`)
    const evLines = m.evs ? STAT_ORDER.filter(s => (m.evs![s] ?? 0) > 0).map(s => `${m.evs![s]} ${STAT_LABELS[s]}`) : []
    const ivStr = ivLines.length ? `\nIVs: ${ivLines.join(' / ')}` : ''
    const evStr = evLines.length ? `\nEVs: ${evLines.join(' / ')}` : ''
    const nature = `\n${m.nature} Nature`
    const moves = m.moves.filter(Boolean).map(mv => `- ${mv}`).join('\n')
    return `${header}${gender}${ability}${level}${shiny}${ivStr}${evStr}${nature}\n${moves}`
  }).join('\n\n')
}

// Inject shiny CSS once
let shinyInjected = false
function injectShinyCSS() {
  if (shinyInjected) return
  shinyInjected = true
  const style = document.createElement('style')
  style.textContent = `
    @keyframes shinyShimmer{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
    .shiny-slot{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460,#533483,#1a1a2e)!important;background-size:300% 300%!important;animation:shinyShimmer 3s ease infinite!important;border-color:#ffd700!important;border-width:2px!important;box-shadow:0 0 6px 1px rgba(255,215,0,0.5)!important;}
    .shiny-list-row{background:linear-gradient(90deg,rgba(255,215,0,0.08),transparent);}
  `
  document.head.appendChild(style)
}

export function BankView({ save, onSaveUpdate, hasPortaPc }: Props) {
  injectShinyCSS()

  const [activeTab, setActiveTab] = useState(0)
  const [activeBox, setActiveBox] = useState(0)
  const [selectedMon, setSelectedMon] = useState<Pokemon | null>(null)
  const [viewMode, setViewMode] = useViewMode('ub_viewMode', 'grid')
  const [loading, setLoading] = useState(false)
  const [dragState, setDragState] = useState<DragState | null>(null)
  const [showSort, setShowSort] = useState(false)
  const [multiSelected, setMultiSelected] = useState<Set<number>>(new Set())
  // selectMode: 'off' | 'select' (move/vault) | 'release'
  const [selectMode, setSelectMode] = useState<'off' | 'select' | 'release'>('off')
  const [searchQuery, setSearchQuery] = useState('')
  const [filterShiny, setFilterShiny] = useState(false)
  const [filterEvo, setFilterEvo] = useState<'off' | 'all' | 'missing'>('off')
  const [specTypes, setSpecTypes] = useState<Record<string, string[]>>({})
  const [evoSet, setEvoSet] = useState<Set<number>>(new Set())
  const [evoFull, setEvoFull] = useState<Record<string, { target_id: number }[]>>({})
  const [dexCaught, setDexCaught] = useState<Set<number>>(new Set())
  const [speciesNational, setSpeciesNational] = useState<Record<string, number>>({})
  const [vault, setVault] = useState<VaultBox[]>([])
  const [pasteText, setPasteText] = useState<string | null>(null)
  const [showMoveOff, setShowMoveOff] = useState(false)
  const [showPresetBox, setShowPresetBox] = useState(false)
  const [shinyToggle, setShinyToggle] = useState(false)
  const [confirmMove, setConfirmMove] = useState(false)
  const [confirmRelease, setConfirmRelease] = useState(true)
  const [baseStatsData, setBaseStatsData] = useState<Record<number, Record<string, number>>>({})
  const [showCalculator, setShowCalculator] = useState(false)

  function enterMode(mode: 'select' | 'release') {
    setSelectMode(mode)
    setMultiSelected(new Set())
  }
  function clearMode() {
    setSelectMode('off')
    setMultiSelected(new Set())
  }

  async function handleViewModeChange(m: ViewMode) {
    setViewMode(m)
    if (m !== 'compact') {
      setPreferences({ list_view: m === 'list' }).catch(() => {})
    }
  }

  useEffect(() => {
    speciesTypes().then(setSpecTypes).catch(() => {})
    evoTable().then(tbl => {
      setEvoSet(new Set(Object.keys(tbl).map(Number)))
      setEvoFull(tbl as unknown as Record<string, { target_id: number }[]>)
    }).catch(() => {})
    dexFlags().then(f => setDexCaught(new Set(f.caught))).catch(() => {})
    speciesToNational().then(setSpeciesNational).catch(() => {})
    loadVault().then(setVault).catch(() => {})
    getPreferences().then(p => {
      setShowPresetBox(p.show_preset_box)
      setViewMode(p.list_view ? 'list' : 'grid')
      setShinyToggle(p.shiny_toggle)
      setConfirmMove(p.confirm_move)
      setConfirmRelease(p.confirm_release)
    }).catch(() => {})
    baseStats().then(setBaseStatsData).catch(() => {})
  }, [])

  const currentSave = useMemo((): SaveData => {
    if (!Object.keys(specTypes).length) return save
    function enrich(mon: Pokemon | null): Pokemon | null {
      if (!mon) return null
      const t = specTypes[String(mon.species)]
      return t ? { ...mon, types: t } : mon
    }
    return {
      ...save,
      party: save.party.map(enrich),
      boxes: save.boxes.map(box => ({
        ...box,
        slots: box.slots.map(slot => ({ ...slot, mon: enrich(slot.mon) })),
      })),
    }
  }, [save, specTypes])

  const effectiveTabs = showPresetBox
    ? [...TABS, { label: 'Preset', filter: (b: { box: number }) => b.box === 26 }]
    : TABS

  const tabBoxes = effectiveTabs[activeTab]
    ? currentSave.boxes.filter(effectiveTabs[activeTab].filter)
    : currentSave.boxes

  const currentBox = tabBoxes[activeBox] ?? tabBoxes[0]

  const allPcBoxes = useMemo(
    () => currentSave.boxes.filter(b => b.box <= 25 || (showPresetBox && b.box === 26)),
    [currentSave.boxes, showPresetBox]
  )

  async function handleDrop(target: { box: number | string; slotNum: number }) {
    if (!dragState) return
    if (dragState.box === target.box && dragState.slotNum === target.slotNum) return
    // Gate party ↔ PC moves behind Porta-PC item ownership
    const isPartyMove = dragState.box === 'party' || target.box === 'party'
    if (isPartyMove && !hasPortaPc) {
      alert('You need the Porta-PC item to move Pokémon between your Party and PC.\n\nEarn it in-game first!')
      return
    }
    if (confirmMove && !confirm('Are you sure you want to perform this action?')) {
      setDragState(null)
      return
    }
    setLoading(true)
    try {
      const updated = await movePokemon([{
        from: { box: dragState.box, slot: dragState.slotNum },
        to: { box: target.box, slot: target.slotNum },
      }])
      onSaveUpdate(updated)
      if (selectedMon) {
        const all = [
          ...updated.party.filter(Boolean),
          ...updated.boxes.flatMap(b => b.slots.map(s => s.mon).filter(Boolean)),
        ] as Pokemon[]
        setSelectedMon(all.find(m => m.pid === selectedMon.pid) ?? null)
      }
    } catch (err) {
      alert('Move failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
      setDragState(null)
    }
  }

  async function handleSort(sortMode: string, scope: string, reserveBoxes: number) {
    setLoading(true)
    try {
      const updated = await sortPC(sortMode, scope, currentBox?.box ?? 1, reserveBoxes)
      onSaveUpdate(updated)
    } catch (err) {
      alert('Sort failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRelease() {
    if (multiSelected.size === 0) return
    const allMons = [
      ...currentSave.party.filter(Boolean),
      ...currentSave.boxes.flatMap(b => b.slots.map(s => s.mon).filter(Boolean)),
    ] as Pokemon[]
    const names = Array.from(multiSelected).map(pid => allMons.find(m => m.pid === pid)?.name ?? '?').join(', ')
    if (confirmRelease && !confirm(`Release ${multiSelected.size} Pokémon? (${names})\nThis cannot be undone.`)) return

    const items: { box: number | string; slot: number }[] = []
    for (const box of currentSave.boxes) {
      for (let i = 0; i < box.slots.length; i++) {
        const mon = box.slots[i].mon
        if (mon && multiSelected.has(mon.pid)) items.push({ box: box.box, slot: i + 1 })
      }
    }
    for (let i = 0; i < currentSave.party.length; i++) {
      const mon = currentSave.party[i]
      if (mon && multiSelected.has(mon.pid)) items.push({ box: 'party', slot: i + 1 })
    }

    setLoading(true)
    try {
      const updated = await releasePokemon(items)
      onSaveUpdate(updated)
      clearMode()
    } catch (err) {
      alert('Release failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSendToVault() {
    if (multiSelected.size === 0) return
    const items: { box: number | string; slot: number }[] = []
    for (const box of currentSave.boxes) {
      for (let i = 0; i < box.slots.length; i++) {
        const mon = box.slots[i].mon
        if (mon && multiSelected.has(mon.pid)) items.push({ box: box.box, slot: i + 1 })
      }
    }
    if (items.length === 0) return
    if (confirmMove && !confirm(`Are you sure you want to perform this action?`)) return
    setLoading(true)
    try {
      const vaultBoxes = await loadVault()
      const emptySlots: { box: number; slot: number }[] = []
      for (const vb of vaultBoxes) {
        for (let i = 0; i < vb.slots.length; i++) {
          if (!vb.slots[i].mon) emptySlots.push({ box: vb.box, slot: i + 1 })
        }
      }
      if (emptySlots.length < items.length) {
        alert(`Not enough vault space (need ${items.length}, have ${emptySlots.length} empty slots)`)
        return
      }
      const depositItems = items.map((item, i) => ({
        from_box: item.box,
        from_slot: item.slot,
        to_vault_box: emptySlots[i].box,
        to_vault_slot: emptySlots[i].slot,
      }))
      const res = await vaultBatchDeposit(depositItems)
      onSaveUpdate(res.save)
      clearMode()
    } catch (err) {
      alert('Vault deposit failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMoveOff(targetBox: number) {
    setShowMoveOff(false)
    if (multiSelected.size === 0) return
    const items: { box: number | string; slot: number }[] = []
    for (const box of currentSave.boxes) {
      for (let i = 0; i < box.slots.length; i++) {
        const mon = box.slots[i].mon
        if (mon && multiSelected.has(mon.pid)) items.push({ box: box.box, slot: i + 1 })
      }
    }
    if (items.length === 0) return
    if (confirmMove && !confirm('Are you sure you want to perform this action?')) return
    setLoading(true)
    try {
      const updated = await moveToBox(items, targetBox)
      onSaveUpdate(updated)
      clearMode()
    } catch (err) {
      alert('Move failed: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function handlePokePaste() {
    // Default: party mons. If multi-selected, use those instead.
    const party = currentSave.party.filter(Boolean) as Pokemon[]
    if (multiSelected.size > 0) {
      const allMons = [
        ...party,
        ...currentSave.boxes.flatMap(b => b.slots.map(s => s.mon).filter(Boolean)),
      ] as Pokemon[]
      const sel = allMons.filter(m => multiSelected.has(m.pid))
      if (sel.length > 0) { setPasteText(makePaste(sel)); return }
    }
    if (party.length === 0) { alert('Party is empty'); return }
    setPasteText(makePaste(party))
  }

  async function handleExportExcel() {
    setLoading(true)
    try { await exportExcel() }
    catch (err) { alert('Export failed: ' + (err as Error).message) }
    finally { setLoading(false) }
  }

  async function handleEvoReport() {
    setLoading(true)
    try { await exportEvolutions() }
    catch (err) { alert('Evo report failed: ' + (err as Error).message) }
    finally { setLoading(false) }
  }

  async function handleUndo() {
    setLoading(true)
    try {
      const newSave = await undo()
      onSaveUpdate(newSave)
      setSelectedMon(null)
      setMultiSelected(new Set())
      clearMode()
    }
    catch (err) { alert('Undo failed: ' + (err as Error).message) }
    finally { setLoading(false) }
  }

  function toggleMultiSelect(mon: Pokemon) {
    setMultiSelected(prev => {
      const next = new Set(prev)
      if (next.has(mon.pid)) next.delete(mon.pid)
      else next.add(mon.pid)
      return next
    })
  }

  function handleSelect(mon: Pokemon) {
    if (selectMode !== 'off') toggleMultiSelect(mon)
    else setSelectedMon(mon)
  }

  const searchLower = searchQuery.toLowerCase().trim()

  // PIDs that appear more than once across PC + vault (same PID = clones or same evolution family)
  const duplicatePids = useMemo(() => {
    const counts = new Map<number, number>()
    for (const box of currentSave.boxes) {
      for (const s of box.slots) {
        if (s.mon) counts.set(s.mon.pid, (counts.get(s.mon.pid) ?? 0) + 1)
      }
    }
    for (const vbox of vault) {
      for (const s of vbox.slots) {
        if (s.mon) counts.set(s.mon.pid, (counts.get(s.mon.pid) ?? 0) + 1)
      }
    }
    return new Set([...counts.entries()].filter(([, n]) => n > 1).map(([pid]) => pid))
  }, [currentSave.boxes, vault])

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
      (evoSet.has(m.species) && ('evolve'.includes(searchLower) || 'can evolve'.includes(searchLower))) ||
      (duplicatePids.has(m.pid) && 'duplicate'.includes(searchLower))
    )
  }

  function monMatchesFilters(m: Pokemon): boolean {
    if (filterShiny && !m.shiny) return false
    if (filterEvo === 'all' && !evoSet.has(m.species)) return false
    if (filterEvo === 'missing') {
      if (!evoSet.has(m.species)) return false
      const targets = evoFull[String(m.species)] ?? []
      // target_id is internal species ID; dexCaught uses national dex numbers — translate before comparing
      const alreadyHaveEvo = targets.some(e => {
        const national = speciesNational[String(e.target_id)] ?? e.target_id
        return dexCaught.has(national)
      })
      if (alreadyHaveEvo) return false
    }
    return true
  }

  const isFiltering = searchLower || filterShiny || filterEvo !== 'off'
  const searchResults = isFiltering
    ? [
        ...currentSave.boxes.flatMap(box =>
          box.slots
            .filter(s => !s.split && s.mon)
            .filter(s => monMatchesSearch(s.mon!) && monMatchesFilters(s.mon!))
            .map(s => s.mon!)
        ),
        ...vault.flatMap(vbox =>
          vbox.slots
            .filter(s => s.mon)
            .filter(s => monMatchesSearch(s.mon!) && monMatchesFilters(s.mon!))
            .map(s => ({ ...s.mon!, box: `vault:${vbox.box}` as any, slot: vbox.slots.indexOf(s) + 1 }))
        )
      ]
    : null

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <PartySidebar
        party={currentSave.party}
        selectedPid={selectedMon?.pid}
        onSelect={handleSelect}
        onDragStart={setDragState}
        onDrop={handleDrop}
        hasPortaPc={hasPortaPc}
        shinyToggle={shinyToggle}
      />

      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        {/* Floating action banner — shown when in select or release mode */}
        {selectMode !== 'off' && (
          <div className="flex items-center gap-3 px-4 py-2 bg-amber-950 border-b border-amber-800 flex-none">
            {selectMode === 'select' ? (
              <>
                <span className="text-amber-200 text-xs font-medium flex-1">
                  {multiSelected.size === 0
                    ? 'Click Pokémon to select — Send to Vault or Move to Box'
                    : `${multiSelected.size} selected — click more, Send to Vault, or Move to Box`}
                </span>
                <button
                  className="px-3 py-1 rounded text-xs font-semibold bg-purple-700 border border-purple-500 text-white hover:bg-purple-600 transition-colors"
                  onClick={handleSendToVault}
                  disabled={multiSelected.size === 0}
                >
                  Send {multiSelected.size > 0 ? multiSelected.size : ''} to Vault
                </button>
                <button
                  className="px-3 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-500 text-white hover:bg-slate-600 transition-colors"
                  onClick={() => setShowMoveOff(true)}
                  disabled={multiSelected.size === 0}
                >
                  Move to Box
                </button>
              </>
            ) : (
              <>
                <span className="text-amber-200 text-xs font-medium flex-1">
                  {multiSelected.size === 0
                    ? 'Click Pokémon to select for release'
                    : `${multiSelected.size} selected for release — click more or confirm`}
                </span>
                <button
                  className="px-3 py-1 rounded text-xs font-semibold bg-red-700 border border-red-600 text-white hover:bg-red-600 transition-colors"
                  onClick={handleRelease}
                  disabled={multiSelected.size === 0}
                >
                  Release {multiSelected.size > 0 ? `${multiSelected.size} Pokémon` : ''}
                </button>
              </>
            )}
            <button
              className="text-amber-400 hover:text-white text-lg leading-none px-1"
              onClick={clearMode}
              title="Cancel"
            >
              ×
            </button>
          </div>
        )}

        {/* Toolbar */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-slate-700 bg-slate-900 flex-none flex-wrap">
          <ViewToggle mode={viewMode as ViewMode} onChange={handleViewModeChange} />
          <div className="w-px h-4 bg-slate-600 mx-0.5" />
          <input
            type="text"
            placeholder="Search by name, nature, ability, item, move, type, shiny, duplicate…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 flex-1 min-w-[180px]"
          />
          {/* Quick filters */}
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${filterShiny ? 'bg-yellow-500 border-yellow-400 text-slate-900' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setFilterShiny(s => !s)}
            title="Show only shiny Pokémon"
          >
            ★ Shiny
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${filterEvo === 'all' ? 'bg-purple-700 border-purple-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setFilterEvo(v => v === 'all' ? 'off' : 'all')}
            title="Show all Pokémon that can evolve"
          >
            Can Evolve
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${filterEvo === 'missing' ? 'bg-orange-600 border-orange-400 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => setFilterEvo(v => v === 'missing' ? 'off' : 'missing')}
            title="Show only Pokémon whose evolution you haven't caught yet"
          >
            Missing Evo
          </button>
          <div className="w-px h-4 bg-slate-600 mx-0.5" />
          <div className="flex-1" />
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${selectMode === 'select' ? 'bg-blue-700 border-blue-500 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => selectMode === 'select' ? clearMode() : enterMode('select')}
            title="Select Pokémon to move or send to Vault"
          >
            Multi-Move
          </button>
          <button
            className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${selectMode === 'release' ? 'bg-red-800 border-red-600 text-white' : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
            onClick={() => selectMode === 'release' ? clearMode() : enterMode('release')}
            title="Select Pokémon to release"
          >
            Release
          </button>
          {selectMode !== 'off' && (
            <>
              <button
                className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
                onClick={() => {
                  const boxPids = currentBox?.slots
                    .map(s => s.mon)
                    .filter(Boolean)
                    .map(m => m!.pid) ?? []
                  setMultiSelected(prev => {
                    const next = new Set(prev)
                    boxPids.forEach(pid => next.add(pid))
                    return next
                  })
                }}
                title="Select all Pokémon in current box"
              >
                Select All
              </button>
              <button
                className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
                onClick={() => setMultiSelected(new Set())}
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
            className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            onClick={() => setShowSort(true)}
          >
            Sort
          </button>
          <button
            className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            onClick={handlePokePaste}
            title="PokéPaste — defaults to party, or use selected Pokémon"
          >
            PokéPaste
          </button>
          <button
            className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            onClick={handleExportExcel}
            title="Export all Pokémon to Excel"
          >
            Export Excel
          </button>
          <button
            className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            onClick={handleEvoReport}
            title="Export evolution report"
          >
            Evo Report
          </button>
          <div className="w-px h-4 bg-slate-600 mx-0.5" />
          <button
            className="px-2 py-1 rounded text-xs font-semibold bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            onClick={() => setShowCalculator(true)}
            title="Calculate stats from IVs/EVs"
          >
            Calculator
          </button>
        </div>

        {isFiltering ? (
          <div className="flex-1 overflow-auto p-2">
            <div className="text-xs text-slate-400 mb-2 px-1 flex items-center gap-2">
              <span>{searchResults?.length ?? 0} results</span>
              {searchLower && <span className="text-slate-500">for "{searchQuery}"</span>}
              {filterShiny && <span className="text-yellow-400">★ Shiny</span>}
              {filterEvo === 'all' && <span className="text-purple-400">Can Evolve</span>}
              {filterEvo === 'missing' && <span className="text-orange-400">Missing Evo</span>}
            </div>
            {searchResults?.map((mon, i) => {
              const isSelected = selectedMon?.pid === mon.pid
              const isMulti = multiSelected.has(mon.pid)
              return (
                <div
                  key={i}
                  className={`flex items-center gap-2 px-2 py-1 rounded border mb-0.5 cursor-pointer text-xs
                    ${isSelected ? 'bg-blue-900 border-blue-500' : isMulti ? 'bg-purple-900 border-purple-500' : 'bg-slate-800 border-slate-700 hover:bg-slate-700'}
                  `}
                  onClick={() => handleSelect(mon)}
                >
                  <span className="text-slate-500">
                    {typeof mon.box === 'string' && mon.box.startsWith('vault:')
                      ? `Vault ${mon.box.replace('vault:', '')} #${mon.slot}`
                      : `Box ${mon.box} #${mon.slot}`}
                  </span>
                  {mon.shiny && <span className="text-yellow-400">★</span>}
                  {evoSet.has(mon.species) && <span className="text-purple-400 text-[9px]">evo</span>}
                  <span className="text-white font-medium">{mon.nick || mon.name}</span>
                  <span className="text-slate-400">Lv.{mon.level}</span>
                  {mon.types?.map(t => (
                    <span key={t} className="px-1 py-0.5 rounded text-[9px] font-bold text-white bg-slate-600">{t}</span>
                  ))}
                </div>
              )
            })}
          </div>
        ) : viewMode === 'compact' ? (
          <CompactBoxView
            boxes={allPcBoxes}
            selectedPid={selectedMon?.pid}
            onSelect={handleSelect}
            onDragStart={setDragState}
            onDrop={handleDrop}
            multiSelected={selectMode !== 'off' ? multiSelected : undefined}
            selectColor={selectMode === 'release' ? 'release' : 'move'}
            evoSet={evoSet}
            shinyToggle={shinyToggle}
          />
        ) : (
          <>
            {viewMode !== 'list' && (
              <>
                <div className="flex gap-0 border-b border-slate-700 bg-slate-900 flex-none overflow-x-auto">
                  {effectiveTabs.map((tab, idx) => (
                    <button
                      key={idx}
                      className={`px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap border-r border-slate-700
                        ${activeTab === idx ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800'}
                      `}
                      onClick={() => { setActiveTab(idx); setActiveBox(0) }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap gap-0.5 px-2 py-1 border-b border-slate-700 bg-slate-900/50 flex-none overflow-x-auto">
                  {tabBoxes.map((box, idx) => (
                    <button
                      key={idx}
                      className={`px-2 py-0.5 text-[10px] rounded transition-colors whitespace-nowrap
                        ${activeBox === idx ? 'bg-blue-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-700'}
                      `}
                      onClick={() => setActiveBox(idx)}
                    >
                      {box.name || `Box ${box.box}`}
                    </button>
                  ))}
                </div>
              </>
            )}

            {currentBox && (
              viewMode === 'list' ? (
                <ListView
                  boxes={allPcBoxes}
                  selectedPid={selectedMon?.pid}
                  onSelect={handleSelect}
                  multiSelected={selectMode !== 'off' ? multiSelected : undefined}
                  selectColor={selectMode === 'release' ? 'release' : 'move'}
                />
              ) : (
                <BoxPanel
                  box={currentBox}
                  viewMode={viewMode as ViewMode}
                  selectedPid={selectedMon?.pid}
                  onSelect={handleSelect}
                  onDragStart={setDragState}
                  onDrop={handleDrop}
                  multiSelected={selectMode !== 'off' ? multiSelected : undefined}
                  selectColor={selectMode === 'release' ? 'release' : 'move'}
                  evoSet={evoSet}
                  shinyToggle={shinyToggle}
                />
              )
            )}
          </>
        )}
      </div>

      <DetailPanel mon={selectedMon} evoFull={evoFull} baseStatsData={baseStatsData} />

      {showSort && (
        <SortModal onClose={() => setShowSort(false)} onSort={handleSort} />
      )}

      {/* PokéPaste modal */}
      {pasteText !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setPasteText(null)}>
          <div className="bg-slate-800 rounded-lg p-4 w-[600px] max-w-[95vw] max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-white font-semibold text-sm">PokéPaste</span>
              <div className="flex gap-2">
                <button
                  className="px-3 py-1 text-xs bg-blue-700 hover:bg-blue-600 text-white rounded"
                  onClick={() => navigator.clipboard.writeText(pasteText).then(() => alert('Copied!'))}
                >
                  Copy
                </button>
                <button className="px-3 py-1 text-xs bg-slate-600 hover:bg-slate-500 text-white rounded" onClick={() => setPasteText(null)}>
                  Close
                </button>
              </div>
            </div>
            <textarea
              className="flex-1 bg-slate-900 text-slate-200 text-xs font-mono p-2 rounded resize-none outline-none overflow-auto"
              value={pasteText}
              readOnly
              rows={20}
            />
          </div>
        </div>
      )}

      {/* Move to Box modal */}
      {showMoveOff && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowMoveOff(false)}>
          <div className="bg-slate-800 rounded-lg p-4 w-80 max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="text-white font-semibold text-sm mb-1">Move {multiSelected.size} Pokémon to box:</div>
            <div className="text-slate-500 text-[10px] mb-2">Grayed boxes don't have enough free slots</div>
            <div className="overflow-auto flex-1">
              {currentSave.boxes.map(box => {
                // Count usable (non-split) empty slots
                const free = box.slots.filter(s => !s.split && !s.mon).length
                const enough = free >= multiSelected.size
                return (
                  <button
                    key={box.box}
                    disabled={!enough}
                    className={`w-full flex items-center justify-between px-3 py-1.5 text-xs rounded transition-colors mb-0.5
                      ${enough ? 'text-slate-300 hover:bg-slate-700 hover:text-white cursor-pointer' : 'text-slate-600 cursor-not-allowed'}
                    `}
                    onClick={() => enough && handleMoveOff(box.box as number)}
                  >
                    <span>{box.name || `Box ${box.box}`}</span>
                    <span className={`text-[10px] ${enough ? 'text-emerald-400' : 'text-slate-600'}`}>{free} free</span>
                  </button>
                )
              })}
            </div>
            <button className="mt-3 px-3 py-1 text-xs bg-slate-600 hover:bg-slate-500 text-white rounded" onClick={() => setShowMoveOff(false)}>
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

      {showCalculator && (
        <IVEVCalculator baseStats={baseStatsData} onClose={() => setShowCalculator(false)} />
      )}
    </div>
  )
}
