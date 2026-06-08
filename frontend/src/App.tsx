import { useState } from 'react'
import type { SaveData, NavTab } from './types/pokemon'
import { loadSave, downloadSave, checkPortaPc, checkUpdate, type UpdateInfo } from './api/client'
import { BankView } from './views/BankView'
import { DexView } from './views/DexView'
import { VaultView } from './views/VaultView'
import { TradeView } from './views/TradeView'
import { SettingsView } from './views/SettingsView'

export default function App() {
  const [saveData, setSaveData] = useState<SaveData | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [activeTab, setActiveTab] = useState<NavTab>('bank')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [hasPortaPc, setHasPortaPc] = useState(false)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)
  const [checkingUpdate, setCheckingUpdate] = useState(false)

  async function handleCheckUpdate() {
    setCheckingUpdate(true)
    setUpdateInfo(null)
    try {
      const info = await checkUpdate()
      setUpdateInfo(info)
    } catch {
      setUpdateInfo({ current: '', up_to_date: false, error: 'Could not reach GitHub' })
    } finally {
      setCheckingUpdate(false)
    }
  }

  function handleSaveUpdate(updated: SaveData) {
    setSaveData(updated)
    setHasChanges(true)
  }

  async function handleFile(file: File) {
    setLoading(true)
    setError('')
    try {
      const data = await loadSave(file)
      setSaveData(data)
      setHasChanges(false)
      checkPortaPc().then(setHasPortaPc).catch(() => setHasPortaPc(false))
    } catch (err) {
      setError((err as Error).message || 'Failed to load save')
    } finally {
      setLoading(false)
    }
  }

  async function handleDownload() {
    try {
      const blob = await downloadSave()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 'save_modified.sav'
      a.click()
      setHasChanges(false)
    } catch {
      alert('Download failed')
    }
  }

  function handleLoadNew() {
    if (hasChanges && !confirm('You have unsaved changes. Load a new save anyway?')) return
    setSaveData(null)
    setHasChanges(false)
    setHasPortaPc(false)
  }

  // Upload screen
  if (!saveData) {
    return (
      <div className="bg-slate-950 text-white h-screen flex flex-col items-center justify-center gap-6">
        <div className="text-center">
          <div className="text-3xl font-black tracking-widest text-white">
            UNBOUND<span className="text-blue-400">BANK</span>
          </div>
          <div className="text-slate-500 text-xs mt-1">v2.0</div>
        </div>

        <div
          className={`
            border-2 border-dashed rounded-xl p-10 w-80 text-center cursor-pointer transition-colors
            ${dragActive ? 'border-blue-400 bg-blue-900/20' : 'border-slate-600 hover:border-slate-500 bg-slate-900'}
          `}
          onClick={() => document.getElementById('file-input')?.click()}
          onDragOver={e => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onDrop={e => {
            e.preventDefault()
            setDragActive(false)
            const file = e.dataTransfer.files[0]
            if (file) handleFile(file)
          }}
        >
          <div className="text-4xl mb-3">💾</div>
          <h2 className="text-white font-bold text-lg mb-1">Drop Save File</h2>
          <p className="text-slate-400 text-sm">
            Drag & drop your .sav file here<br />or click to browse
          </p>
          <input
            id="file-input"
            type="file"
            accept=".sav,.sa1,.sa2,.sa3,.sa4,.srm,.SaveRAM"
            className="hidden"
            onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]) }}
          />
        </div>

        {error && <div className="text-red-400 text-sm">{error}</div>}
        {loading && <div className="text-slate-400 text-sm animate-pulse">LOADING...</div>}
      </div>
    )
  }

  const t = saveData.trainer

  const NAV_TABS: { key: NavTab; label: string }[] = [
    { key: 'bank',  label: 'Bank' },
    { key: 'dex',   label: 'Pokédex' },
    { key: 'vault', label: 'Vault' },
    { key: 'trade', label: 'Trade' },
    { key: 'settings', label: 'Settings' },
  ]

  return (
    <div className="bg-slate-950 text-white h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-2 bg-slate-900 border-b border-slate-700 flex-none">
        {/* Logo */}
        <div className="text-base font-black tracking-widest mr-2 flex-none">
          UNBOUND<span className="text-blue-400">BANK</span>
        </div>

        {/* Nav tabs */}
        <nav className="flex gap-0.5">
          {NAV_TABS.map(({ key, label }) => (
            <button
              key={key}
              className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors ${activeTab === key ? 'bg-blue-700 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}
              onClick={() => setActiveTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="flex-1" />

        {/* Trainer info */}
        <div className="flex items-center gap-3 text-xs text-slate-300">
          <TrainerStat label="Trainer" value={`${t.name} ${t.gender}`} />
          <TrainerStat label="ID" value={String(t.tid).padStart(5, '0')} />
          <TrainerStat label="Money" value={t.money} />
          <TrainerStat label="Badges" value={String(t.badges)} />
          <TrainerStat label="Time" value={t.playtime} />
        </div>

        {/* Unsaved badge */}
        {hasChanges && (
          <span className="px-2 py-0.5 rounded bg-amber-600 text-white text-[10px] font-bold uppercase tracking-wider">
            Unsaved
          </span>
        )}

        {/* Update check */}
        <div className="flex items-center gap-1.5">
          <button
            className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-400 hover:bg-slate-600 transition-colors disabled:opacity-50"
            onClick={handleCheckUpdate}
            disabled={checkingUpdate}
            title="Check for a newer release on GitHub"
          >
            {checkingUpdate ? '...' : 'Check for Updates'}
          </button>
          {updateInfo && !updateInfo.error && updateInfo.up_to_date && (
            <span className="text-[10px] text-emerald-400">v{updateInfo.current} ✓ Up to date</span>
          )}
          {updateInfo && !updateInfo.error && !updateInfo.up_to_date && (
            <a
              href={updateInfo.release_url}
              target="_blank"
              rel="noreferrer"
              className="text-[10px] text-amber-400 hover:text-amber-300 underline"
            >
              v{updateInfo.latest} available ↗
            </a>
          )}
          {updateInfo?.error && (
            <span className="text-[10px] text-red-400">{updateInfo.error}</span>
          )}
        </div>

        {/* Actions */}
        <button
          className="px-2 py-1 rounded text-xs bg-slate-700 border border-slate-600 text-slate-300 hover:bg-slate-600 transition-colors"
          onClick={handleLoadNew}
        >
          Load New
        </button>
        <button
          className={`px-2 py-1 rounded text-xs font-semibold border transition-colors ${hasChanges ? 'bg-blue-700 border-blue-600 text-white hover:bg-blue-600' : 'bg-slate-800 border-slate-700 text-slate-500 cursor-not-allowed'}`}
          onClick={handleDownload}
          disabled={!hasChanges}
        >
          Download Save
        </button>
      </header>

      {/* Content */}
      <main className="flex flex-1 min-h-0 overflow-hidden">
        {activeTab === 'bank'     && <BankView  save={saveData} onSaveUpdate={handleSaveUpdate} hasPortaPc={hasPortaPc} />}
        {activeTab === 'dex'      && <DexView />}
        {activeTab === 'vault'    && <VaultView save={saveData} onSaveUpdate={handleSaveUpdate} />}
        {activeTab === 'trade'    && <TradeView save={saveData} onSaveUpdate={handleSaveUpdate} />}
        {activeTab === 'settings' && <SettingsView />}
      </main>
    </div>
  )
}

function TrainerStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-[9px] text-slate-500 uppercase tracking-wider">{label}</span>
      <span className="text-xs text-slate-200 font-medium">{value}</span>
    </div>
  )
}
