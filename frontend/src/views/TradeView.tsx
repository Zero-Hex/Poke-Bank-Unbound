import { useState, useEffect, useRef } from 'react'
import type { SaveData, Pokemon, Box, VaultBox, TradeSecondaryStatus, ViewMode } from '../types/pokemon'
import {
  loadSecondary, unloadSecondary, tradeTransfer, tradeSwap,
  savePrimary, saveSecondary, tradeSecondaryStatus, tradeVaultData,
  currentSave as fetchCurrentSave, movePokemon,
} from '../api/client'
import { BoxPanel } from '../components/BoxPanel'
import { DetailPanel } from '../components/DetailPanel'
import { ViewToggle } from '../components/ViewToggle'
import { ListView } from '../components/ListView'
import { Sprite } from '../components/Sprite'

interface Props {
  save: SaveData
  onSaveUpdate: (s: SaveData) => void
}

type Side = 'primary' | 'secondary'

interface DragState {
  box: number | string
  slotNum: number
  mon: Pokemon
  side: Side
  fromVault: boolean
}

interface PendingExchange {
  mon: Pokemon
  side: Side
  fromVault: boolean
}

interface TradeTab {
  label: string
  isVault: boolean
  filter: (b: { box: number }) => boolean
}

const PC_TABS: TradeTab[] = [
  { label: '1–10',  isVault: false, filter: b => b.box >= 1  && b.box <= 10 },
  { label: '11–20', isVault: false, filter: b => b.box >= 11 && b.box <= 20 },
  { label: '21–24', isVault: false, filter: b => b.box >= 21 && b.box <= 24 },
]
const VAULT_TABS: TradeTab[] = [
  { label: '🏠 1–10',  isVault: true, filter: b => b.box >= 1  && b.box <= 10 },
  { label: '🏠 11–20', isVault: true, filter: b => b.box >= 11 && b.box <= 20 },
  { label: '🏠 21–30', isVault: true, filter: b => b.box >= 21 && b.box <= 30 },
]
const ALL_TABS = [...PC_TABS, ...VAULT_TABS]

function vaultToBox(vb: VaultBox): Box {
  return { box: vb.box, name: vb.name, slots: vb.slots.map(s => ({ mon: s.mon ?? null })) }
}

function TradePaneBoxes({
  pcBoxes, vaultBoxes, label, colorClass, viewMode,
  selectedMon, onSelect, onDragStart, onDrop, side,
  exchangeMode, pendingPid, onExchangeSelect,
}: {
  pcBoxes: Box[]
  vaultBoxes: VaultBox[]
  label: string
  colorClass: string
  viewMode: ViewMode
  selectedMon: Pokemon | null
  onSelect: (mon: Pokemon) => void
  onDragStart: (ds: DragState) => void
  onDrop: (target: { box: number | string; slotNum: number; toVault: boolean }) => void
  side: Side
  exchangeMode: boolean
  pendingPid: number | null
  onExchangeSelect: (mon: Pokemon, fromVault: boolean) => void
}) {
  const [activeTabIdx, setActiveTabIdx] = useState(0)
  const [activeBox, setActiveBox] = useState(0)

  const activeTab = ALL_TABS[activeTabIdx] ?? ALL_TABS[0]
  const boxes = activeTab.isVault
    ? vaultBoxes.filter(activeTab.filter).map(vaultToBox)
    : pcBoxes.filter(activeTab.filter)
  const currentBox = boxes[activeBox] ?? boxes[0]

  function switchTab(idx: number) {
    setActiveTabIdx(idx)
    setActiveBox(0)
  }

  const highlightPids = pendingPid ? new Set([pendingPid]) : undefined

  function handleSelect(mon: Pokemon) {
    onSelect(mon)
    if (exchangeMode) onExchangeSelect(mon, activeTab.isVault)
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      <div className={`px-3 py-1.5 border-b border-slate-700 ${colorClass} flex-none`}>
        <span className="text-white font-bold text-sm">{label}</span>
      </div>

      {/* All tab buttons in one scrollable row */}
      <div className="flex gap-0 border-b border-slate-700 bg-slate-900 flex-none overflow-x-auto">
        {ALL_TABS.map((tab, idx) => (
          <button
            key={idx}
            className={`px-3 py-1 text-xs font-medium border-r border-slate-700 transition-colors whitespace-nowrap
              ${activeTabIdx === idx
                ? tab.isVault ? 'bg-purple-800 text-white' : 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'}
            `}
            onClick={() => switchTab(idx)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Box sub-tabs */}
      <div className="flex flex-wrap gap-0.5 px-2 py-1 border-b border-slate-700 bg-slate-900/50 flex-none overflow-x-auto">
        {boxes.map((box, idx) => (
          <button
            key={idx}
            className={`px-2 py-0.5 text-[10px] rounded transition-colors whitespace-nowrap
              ${activeBox === idx
                ? side === 'primary' ? 'bg-blue-700 text-white' : 'bg-green-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-700'}
            `}
            onClick={() => setActiveBox(idx)}
          >
            {box.name || `Box ${box.box}`}
          </button>
        ))}
        {boxes.length === 0 && <span className="text-slate-600 text-[10px] px-2">No boxes</span>}
      </div>

      {/* Box content */}
      {currentBox && (
        viewMode === 'grid' ? (
          <BoxPanel
            box={currentBox}
            viewMode={viewMode}
            selectedPid={!exchangeMode ? selectedMon?.pid : undefined}
            onSelect={handleSelect}
            onDragStart={slot => onDragStart({ ...slot, side, fromVault: activeTab.isVault })}
            onDrop={target => onDrop({ ...target, toVault: activeTab.isVault })}
            highlightPids={highlightPids}
          />
        ) : (
          <ListView
            boxes={[currentBox]}
            selectedPid={!exchangeMode ? selectedMon?.pid : undefined}
            onSelect={handleSelect}
            multiSelected={undefined}
            selectColor="move"
          />
        )
      )}
    </div>
  )
}

export function TradeView({ save, onSaveUpdate }: Props) {
  const [secondary, setSecondary] = useState<TradeSecondaryStatus>({ loaded: false })
  const [vaultData, setVaultData] = useState<{ primary: VaultBox[]; secondary: VaultBox[] } | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedMon, setSelectedMon] = useState<Pokemon | null>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)
  const [exchangeMode, setExchangeMode] = useState(false)
  const [pendingExchange, setPendingExchange] = useState<PendingExchange | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    tradeSecondaryStatus().then(setSecondary).catch(() => {})
    tradeVaultData().then(setVaultData).catch(() => {})
  }, [])

  function toggleExchangeMode() {
    setExchangeMode(prev => !prev)
    setPendingExchange(null)
    setSelectedMon(null)
  }

  async function withLoading<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setLoading(true)
    try { return await fn() }
    catch (err) { alert((err as Error).message) }
    finally { setLoading(false) }
  }

  async function refreshAll() {
    const [updated, status, vault] = await Promise.all([
      fetchCurrentSave(),
      tradeSecondaryStatus(),
      tradeVaultData(),
    ])
    onSaveUpdate(updated)
    setSecondary(status)
    setVaultData(vault)
  }

  async function handleLoadSecondary(file: File) {
    await withLoading(async () => {
      await loadSecondary(file)
      await refreshAll()
    })
  }

  async function handleUnload() {
    if (!confirm('Unload secondary save? Any unsaved changes will be lost.')) return
    await withLoading(unloadSecondary)
    setSecondary({ loaded: false })
    setExchangeMode(false)
    setPendingExchange(null)
    const vault = await tradeVaultData().catch(() => null)
    if (vault) setVaultData(vault)
  }

  function handleExchangeSelect(mon: Pokemon, side: Side, fromVault: boolean) {
    if (!pendingExchange) {
      // Stage this mon
      setPendingExchange({ mon, side, fromVault })
      setSelectedMon(mon)
      return
    }
    if (pendingExchange.mon.pid === mon.pid) {
      // Same mon clicked again — deselect
      setPendingExchange(null)
      setSelectedMon(null)
      return
    }
    if (pendingExchange.side === side) {
      // Same side — change selection to new mon
      setPendingExchange({ mon, side, fromVault })
      setSelectedMon(mon)
      return
    }

    // Different side — execute swap
    const priSrc = pendingExchange.side === 'primary' ? pendingExchange : { mon, fromVault }
    const secSrc = pendingExchange.side === 'secondary' ? pendingExchange : { mon, fromVault }

    withLoading(async () => {
      const result = await tradeSwap({
        pri_box: priSrc.mon.box,
        pri_slot: priSrc.mon.slot,
        sec_box: secSrc.mon.box,
        sec_slot: secSrc.mon.slot,
        pri_vault: priSrc.fromVault,
        sec_vault: secSrc.fromVault,
      })
      onSaveUpdate(result.primary)
      setSecondary(prev => ({ ...prev, save: result.secondary }))
      setPendingExchange(null)
      setSelectedMon(null)
    })
  }

  async function handleDrop(
    fromState: DragState,
    target: { box: number | string; slotNum: number; toVault: boolean }
  ) {
    if (fromState.box === target.box && fromState.slotNum === target.slotNum && fromState.side === (target.toVault ? 'vault' : fromState.side)) return

    const baseDir = fromState.side === 'primary' ? 'primary_to_secondary' : 'secondary_to_primary'
    const direction = target.toVault ? `${baseDir}_vault` : baseDir

    await withLoading(async () => {
      await tradeTransfer({
        direction: direction as import('../api/client').TradeDirection,
        from_box: fromState.box,
        from_slot: fromState.slotNum,
        to_box: target.box,
        to_slot: target.slotNum,
        from_vault: fromState.fromVault,
      })
      await refreshAll()
    })
    setDragState(null)
  }

  async function handleSameSideDrop(
    fromState: DragState,
    target: { box: number | string; slotNum: number; toVault: boolean },
    side: Side
  ) {
    if (fromState.side !== side) {
      await handleDrop(fromState, target)
      return
    }
    if (fromState.box === target.box && fromState.slotNum === target.slotNum) return
    await withLoading(async () => {
      if (side === 'primary') {
        const updated = await movePokemon([{
          from: { box: fromState.box, slot: fromState.slotNum },
          to:   { box: target.box,    slot: target.slotNum    },
        }])
        onSaveUpdate(updated)
      } else {
        // Within secondary: use tradeSwap to swap the two slots
        await tradeSwap({
          pri_box: fromState.box, pri_slot: fromState.slotNum,
          sec_box: target.box,   sec_slot: target.slotNum,
        })
        const status = await tradeSecondaryStatus()
        setSecondary(status)
      }
    })
    setDragState(null)
  }

  const secBoxes: Box[] = secondary.save?.boxes ?? []

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">

        {/* Exchange mode banner */}
        {exchangeMode && (
          <div className="flex items-center gap-3 px-4 py-2 bg-amber-950 border-b border-amber-800 flex-none">
            {pendingExchange ? (
              <>
                <Sprite speciesId={pendingExchange.mon.species} shiny={pendingExchange.mon.shiny} size={24} />
                <span className="text-amber-200 text-xs font-medium flex-1">
                  <span className="font-bold">{pendingExchange.mon.nick || pendingExchange.mon.name}</span>
                  {' '}({pendingExchange.side === 'primary' ? 'Primary' : 'Secondary'}) staged —{' '}
                  click a Pokémon on the <span className="font-bold">{pendingExchange.side === 'primary' ? 'Secondary' : 'Primary'}</span> side to exchange
                </span>
                <button
                  className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600"
                  onClick={() => { setPendingExchange(null); setSelectedMon(null) }}
                >
                  Deselect
                </button>
              </>
            ) : (
              <span className="text-amber-200 text-xs font-medium flex-1">
                Exchange Mode — click a Pokémon on either side to stage it for trading
              </span>
            )}
            <button className="text-amber-400 hover:text-white text-lg leading-none px-1" onClick={toggleExchangeMode} title="Exit exchange mode">×</button>
          </div>
        )}

        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-1.5 border-b border-slate-700 bg-slate-900 flex-none">
          <span className="text-white font-bold text-sm">Trade</span>
          {secondary.loaded && secondary.trainer && (
            <span className="text-slate-400 text-xs">
              Sec: {secondary.trainer.name} #{String(secondary.trainer.tid).padStart(5, '0')}
            </span>
          )}
          <div className="flex-1" />
          <ViewToggle mode={viewMode} onChange={setViewMode} />
          {secondary.loaded && (
            <button
              className={`px-2 py-1 rounded text-xs font-semibold border transition-colors
                ${exchangeMode
                  ? 'bg-amber-700 border-amber-500 text-white'
                  : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'}`}
              onClick={toggleExchangeMode}
              title="Select a Pokémon on each side to swap them"
            >
              ⇄ Exchange
            </button>
          )}
          <button
            className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
            onClick={() => withLoading(savePrimary)}
          >
            ↓ Pri
          </button>
          {secondary.loaded && (
            <>
              <button
                className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
                onClick={() => withLoading(saveSecondary)}
              >
                ↓ Sec
              </button>
              <button
                className="px-2 py-1 rounded text-xs bg-red-800 border border-red-700 text-white hover:bg-red-700 transition-colors"
                onClick={handleUnload}
              >
                Unload
              </button>
            </>
          )}
        </div>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Primary pane */}
          <TradePaneBoxes
            pcBoxes={save.boxes}
            vaultBoxes={vaultData?.primary ?? []}
            label={`Primary${save.trainer ? ` — ${save.trainer.name} #${String(save.trainer.tid).padStart(5, '0')}` : ''}`}
            colorClass="bg-blue-900/40"
            viewMode={viewMode}
            selectedMon={selectedMon}
            onSelect={setSelectedMon}
            onDragStart={setDragState}
            onDrop={target => {
              if (!dragState) return
              handleSameSideDrop(dragState, target, 'primary')
            }}
            side="primary"
            exchangeMode={exchangeMode}
            pendingPid={pendingExchange?.side === 'primary' ? pendingExchange.mon.pid : null}
            onExchangeSelect={(mon, fromVault) => handleExchangeSelect(mon, 'primary', fromVault)}
          />

          <div className="w-px bg-slate-700 flex-none" />

          {/* Secondary pane */}
          {!secondary.loaded ? (
            <div
              className="flex-1 flex flex-col items-center justify-center bg-slate-900 gap-3 cursor-pointer"
              onDragOver={e => e.preventDefault()}
              onDrop={e => {
                e.preventDefault()
                const file = e.dataTransfer.files[0]
                if (file) handleLoadSecondary(file)
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="text-slate-300 font-bold text-lg">Load Second Save</div>
              <p className="text-slate-500 text-sm text-center">Drop a .sav file here<br />or click to browse</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".sav,.sa1,.sa2,.sa3,.sa4,.srm,.SaveRAM"
                className="hidden"
                onChange={e => { if (e.target.files?.[0]) handleLoadSecondary(e.target.files[0]) }}
              />
              <button
                className="px-4 py-2 rounded bg-green-700 text-white text-sm font-semibold hover:bg-green-600"
                onClick={e => { e.stopPropagation(); fileInputRef.current?.click() }}
              >
                Browse…
              </button>
            </div>
          ) : (
            <TradePaneBoxes
              pcBoxes={secBoxes}
              vaultBoxes={vaultData?.secondary ?? []}
              label={`Secondary${secondary.trainer ? ` — ${secondary.trainer.name} #${String(secondary.trainer.tid).padStart(5, '0')}` : ''}`}
              colorClass="bg-green-900/40"
              viewMode={viewMode}
              selectedMon={selectedMon}
              onSelect={setSelectedMon}
              onDragStart={setDragState}
              onDrop={target => {
                if (!dragState) return
                handleSameSideDrop(dragState, target, 'secondary')
              }}
              side="secondary"
              exchangeMode={exchangeMode}
              pendingPid={pendingExchange?.side === 'secondary' ? pendingExchange.mon.pid : null}
              onExchangeSelect={(mon, fromVault) => handleExchangeSelect(mon, 'secondary', fromVault)}
            />
          )}
        </div>
      </div>

      <DetailPanel mon={selectedMon} />

      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 pointer-events-none">
          <div className="bg-slate-800 px-6 py-3 rounded-lg text-white text-sm font-semibold">LOADING...</div>
        </div>
      )}
    </div>
  )
}
