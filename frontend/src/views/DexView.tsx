import { useState, useEffect, useMemo } from 'react'
import { dexFlags, dexSpeciesJson, speciesTypes, evoTable, getPreferences, setPreferences, type DexSpeciesEntry } from '../api/client'
import { useSpriteManifest, spriteUrl } from '../hooks/useSprites'

const ALL_TYPES = [
  'Normal','Fire','Water','Grass','Electric','Ice','Fighting','Poison',
  'Ground','Flying','Psychic','Bug','Rock','Ghost','Dragon','Dark','Steel','Fairy',
]

type Filter = 'all' | 'caught' | 'seen' | 'missing' | 'evolve'
type DexTab = 'national' | 'borrius'

interface SpeciesCard {
  id: number
  entry: DexSpeciesEntry
  types: string[]
  canEvo: boolean
  isCaught: boolean
  isSeen: boolean
  sortKey: number
}

export function DexView() {
  const manifest = useSpriteManifest()
  const [caught, setCaught] = useState<Set<number>>(new Set())
  const [seen, setSeen] = useState<Set<number>>(new Set())
  const [dexSpecies, setDexSpecies] = useState<Record<string, DexSpeciesEntry>>({})
  const [typeMap, setTypeMap] = useState<Record<string, string[]>>({})
  const [evoSpecies, setEvoSpecies] = useState<Set<number>>(new Set())
  const [locations, setLocations] = useState<Record<string, { locations: string[] }>>({})
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('all')
  const [typeFilter, setTypeFilter] = useState('')
  const [search, setSearch] = useState('')
  const [spoilers, setSpoilers] = useState(true)
  const [showShiny, setShowShiny] = useState(false)
  const [tab, setTab] = useState<DexTab>('national')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      dexFlags(),
      dexSpeciesJson(),
      speciesTypes(),
      evoTable(),
      fetch('/borrius_locations.json').then(r => r.json()).catch(() => ({})),
      getPreferences()
    ])
      .then(([flags, species, types, evo, locs, prefs]) => {
        setCaught(new Set(flags.caught))
        setSeen(new Set(flags.seen))
        setDexSpecies(species)
        setTypeMap(types)
        setEvoSpecies(new Set(Object.keys(evo).map(Number)))
        setLocations(locs)
        setSpoilers(prefs.spoilers_on)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const cards: SpeciesCard[] = useMemo(() => {
    return Object.entries(dexSpecies).map(([id, entry]) => ({
      id: Number(id),
      entry,
      types: typeMap[id] || [],
      canEvo: evoSpecies.has(Number(id)),
      isCaught: caught.has(entry.national),
      isSeen: seen.has(entry.national),
      sortKey: tab === 'borrius' ? (entry.borrius || 99999) : (entry.national || 99999),
    }))
  }, [dexSpecies, typeMap, evoSpecies, caught, seen, tab])

  const filtered = useMemo(() => {
    let list = cards
    if (tab === 'borrius') list = list.filter(c => c.entry.borrius > 0)
    list = [...list].sort((a, b) => a.sortKey - b.sortKey)
    if (filter === 'caught') list = list.filter(c => c.isCaught)
    else if (filter === 'seen') list = list.filter(c => c.isSeen && !c.isCaught)
    else if (filter === 'missing') list = list.filter(c => !c.isCaught)
    else if (filter === 'evolve') list = list.filter(c => c.canEvo)
    if (typeFilter) list = list.filter(c => c.types.includes(typeFilter))
    if (search.trim()) {
      const q = search.toLowerCase().trim()
      list = list.filter(c => c.entry.name.toLowerCase().includes(q))
    }
    return list
  }, [cards, filter, typeFilter, search, tab])

  const totalInTab = tab === 'borrius' ? cards.filter(c => c.entry.borrius > 0).length : cards.length
  const caughtInTab = tab === 'borrius'
    ? cards.filter(c => c.entry.borrius > 0 && c.isCaught).length
    : cards.filter(c => c.isCaught).length
  const seenInTab = tab === 'borrius'
    ? cards.filter(c => c.entry.borrius > 0 && c.isSeen).length
    : cards.filter(c => c.isSeen).length
  const pct = totalInTab > 0 ? ((caughtInTab / totalInTab) * 100).toFixed(1) : '0.0'

  function handleToggleSpoilers() {
    const newVal = !spoilers
    setSpoilers(newVal)
    setPreferences({ spoilers_on: newVal }).catch(() => {})
  }

  function handleToggleShiny() {
    setShowShiny(s => !s)
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-950">
        <div className="text-slate-400 text-sm">Loading Pokédex…</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden bg-slate-950">
      {/* Stats bar */}
      <div className="flex items-center gap-6 px-4 py-2 bg-slate-900 border-b border-slate-700 flex-none">
        <div className="flex gap-4 text-xs">
          <div>
            <div className="text-slate-500 uppercase tracking-wide text-[10px]">Caught</div>
            <div className="text-white font-bold text-lg leading-tight">{caughtInTab}<span className="text-slate-500 font-normal text-sm">/{totalInTab}</span></div>
          </div>
          <div>
            <div className="text-slate-500 uppercase tracking-wide text-[10px]">Seen</div>
            <div className="text-white font-bold text-lg leading-tight">{seenInTab}</div>
          </div>
          <div>
            <div className="text-slate-500 uppercase tracking-wide text-[10px]">Completion</div>
            <div className="text-white font-bold text-lg leading-tight">{pct}%</div>
          </div>
        </div>
        <div className="flex-1 max-w-xs">
          <div className="h-3 rounded-full bg-slate-700 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-400 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">{seenInTab} seen ({((seenInTab/Math.max(totalInTab,1))*100).toFixed(1)}%)</div>
        </div>
        <div className="text-xs text-slate-500 ml-auto">{totalInTab - caughtInTab} remaining</div>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-0 px-4 border-b border-slate-700 bg-slate-900 flex-none">
        {(['national','borrius'] as DexTab[]).map(t => (
          <button
            key={t}
            className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors uppercase tracking-wide
              ${tab === t ? 'border-blue-500 text-white' : 'border-transparent text-slate-500 hover:text-slate-300'}
            `}
            onClick={() => setTab(t)}
          >
            {t === 'national' ? 'National Pokédex' : 'Borrius Pokédex'}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-700 bg-slate-900/60 flex-none flex-wrap">
        {(['all','caught','seen','missing','evolve'] as Filter[]).map(f => (
          <button
            key={f}
            className={`px-3 py-1 rounded text-xs font-semibold uppercase tracking-wide transition-colors
              ${filter === f ? 'bg-blue-700 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}
            `}
            onClick={() => setFilter(f)}
          >
            {f === 'evolve' ? 'Can Evolve' : f}
          </button>
        ))}
        <select
          className="bg-slate-800 border border-slate-600 text-slate-300 text-xs rounded px-2 py-1 focus:outline-none"
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
        >
          <option value="">All Types</option>
          {ALL_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input
          type="text"
          placeholder="Search name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 w-36"
        />
        <div className="ml-auto flex items-center gap-2">
          <button
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${showShiny ? 'bg-yellow-500 text-slate-900' : 'bg-slate-700 text-slate-300 hover:text-white'}`}
            onClick={handleToggleShiny}
            title="Toggle shiny sprites"
          >
            ★ Shiny
          </button>
          <button
            className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${spoilers ? 'bg-slate-700 text-white' : 'bg-amber-700 text-white'}`}
            onClick={handleToggleSpoilers}
            title="Toggle name/sprite spoilers for unseen Pokémon"
          >
            Spoilers: {spoilers ? 'ON' : 'OFF'}
          </button>
        </div>
        <span className="text-xs text-slate-500">{filtered.length} shown</span>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto p-3">
        <div className="grid gap-1.5" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))' }}>
          {filtered.map(card => {
            const url = spriteUrl(manifest, card.id, showShiny)
            const reveal = spoilers || card.isSeen || card.isCaught
            const dexNum = tab === 'borrius' ? card.entry.borrius : card.entry.national
            return (
              <div
                key={card.id}
                onClick={() => setSelectedId(card.id)}
                className={`
                  relative flex flex-col items-center rounded border-2 p-1.5 select-none cursor-pointer hover:brightness-110 transition-all
                  ${card.isCaught ? 'border-emerald-600 bg-slate-800' : card.isSeen ? 'border-blue-700 bg-slate-900' : 'border-slate-800 bg-slate-950 opacity-60'}
                `}
                title={reveal ? `#${dexNum} ${card.entry.name}${card.canEvo ? ' — Can evolve' : ''}` : `#${dexNum}`}
              >
                {/* Dex number */}
                <span className="text-[8px] text-slate-500 self-start leading-none mb-0.5">#{dexNum}</span>
                {/* Sprite */}
                {url ? (
                  <img
                    src={url}
                    width={80}
                    height={80}
                    alt=""
                    style={{
                      objectFit: 'contain',
                      imageRendering: 'pixelated',
                      filter: reveal ? 'none' : 'brightness(0)',
                    }}
                    onError={e => {
                      const fallback = spriteUrl(manifest, card.id, false)
                      if (fallback) (e.target as HTMLImageElement).src = fallback
                    }}
                  />
                ) : (
                  <div className="w-20 h-20 flex items-center justify-center text-slate-600 text-xs">?</div>
                )}
                {/* Name */}
                <span className={`text-[9px] text-center leading-tight mt-0.5 ${card.isCaught ? 'text-white' : 'text-slate-400'}`}>
                  {reveal ? card.entry.name : '???'}
                </span>
                {/* Type badges */}
                {reveal && card.types.length > 0 && (
                  <div className="flex gap-0.5 mt-0.5 flex-wrap justify-center">
                    {card.types.map(t => (
                      <TypePill key={t} type={t} />
                    ))}
                  </div>
                )}
                {/* Status indicator */}
                {card.isCaught && (
                  <span className="absolute top-0.5 right-0.5 text-[8px] text-emerald-400">✓</span>
                )}
                {!card.isCaught && card.isSeen && (
                  <span className="absolute top-0.5 right-0.5 text-[8px] text-blue-400">👁</span>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Detail Modal */}
      {selectedId !== null && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
          onClick={() => setSelectedId(null)}
        >
          <div
            className="bg-slate-900 rounded-lg p-6 max-w-sm w-96 border border-slate-700"
            onClick={e => e.stopPropagation()}
          >
            {(() => {
              const card = filtered.find(c => c.id === selectedId)
              if (!card) return null
              const dexNum = tab === 'borrius' ? card.entry.borrius : card.entry.national
              const locationData = locations[card.entry.name]
              const url = spriteUrl(manifest, card.id, showShiny)
              return (
                <>
                  <div className="flex gap-4 items-start">
                    <div className="flex flex-col items-center">
                      {url && (
                        <img
                          src={url}
                          width={120}
                          height={120}
                          alt=""
                          style={{ objectFit: 'contain', imageRendering: 'pixelated' }}
                        />
                      )}
                      <span className="text-slate-400 text-sm mt-2">#{dexNum}</span>
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-white mb-1">{card.entry.name}</h3>
                      {card.types.length > 0 && (
                        <div className="flex gap-1 mb-3 flex-wrap">
                          {card.types.map(t => <TypePill key={t} type={t} />)}
                        </div>
                      )}
                      {card.canEvo && (
                        <p className="text-purple-300 text-xs mb-2">✓ Can evolve</p>
                      )}
                      {card.isCaught && (
                        <p className="text-emerald-400 text-xs mb-2">✓ Caught</p>
                      )}
                    </div>
                  </div>
                  {locationData && locationData.locations.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-700">
                      <p className="text-slate-400 text-xs uppercase tracking-wide mb-2">Where to find</p>
                      <ul className="space-y-0.5 max-h-40 overflow-y-auto pr-1">
                        {locationData.locations.map((loc, i) => (
                          <li key={i} className="text-slate-200 text-xs">{loc}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <button
                    onClick={() => setSelectedId(null)}
                    className="mt-4 w-full py-2 bg-slate-700 hover:bg-slate-600 text-white rounded text-xs font-semibold transition-colors"
                  >
                    Close
                  </button>
                </>
              )
            })()}
          </div>
        </div>
      )}
    </div>
  )
}

const TYPE_COLORS: Record<string, string> = {
  Normal:'#9099A1', Fire:'#E62829', Water:'#2980EF', Grass:'#3FA129', Electric:'#FAC000',
  Ice:'#3DCEF3', Fighting:'#FF8000', Poison:'#9141CB', Ground:'#915121', Flying:'#81B9EF',
  Psychic:'#EF4179', Bug:'#91A119', Rock:'#AFA981', Ghost:'#704170', Dragon:'#5060E1',
  Dark:'#624D4E', Steel:'#60A1B8', Fairy:'#EF70EF',
}

// Determine if a hex color is light or dark
function isLightColor(hex: string): boolean {
  const color = hex.replace('#', '')
  const r = parseInt(color.substr(0, 2), 16)
  const g = parseInt(color.substr(2, 2), 16)
  const b = parseInt(color.substr(4, 2), 16)
  // Calculate luminance using WCAG formula
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.5
}

function TypePill({ type }: { type: string }) {
  const bgColor = TYPE_COLORS[type] || '#666'
  const textColor = isLightColor(bgColor) ? '#1e293b' : '#ffffff'
  return (
    <span
      className="px-1 rounded text-[7px] font-bold"
      style={{ background: bgColor, color: textColor }}
    >
      {type}
    </span>
  )
}
