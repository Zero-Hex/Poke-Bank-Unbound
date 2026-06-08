import { useState } from 'react'

interface Props {
  baseStats?: Record<number, Record<string, number>>
  onClose?: () => void
}

// Note: baseStats param is kept for future use (species-specific calculations)

const NATURES = [
  'Hardy', 'Lonely', 'Brave', 'Adamant', 'Naughty',
  'Bold', 'Docile', 'Relaxed', 'Impish', 'Lax',
  'Timid', 'Hasty', 'Serious', 'Jolly', 'Naive',
  'Modest', 'Mild', 'Quiet', 'Bashful', 'Rash',
  'Calm', 'Gentle', 'Sassy', 'Careful', 'Quirky',
]

const STAT_KEYS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'] as const
const STAT_LABELS = ['HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe']

const NATURE_BOOSTS = {
  'Hardy': {}, 'Docile': {}, 'Serious': {}, 'Bashful': {}, 'Quirky': {},
  'Lonely': { atk: 1.1, def: 0.9 }, 'Brave': { atk: 1.1, spe: 0.9 },
  'Adamant': { atk: 1.1, spa: 0.9 }, 'Naughty': { atk: 1.1, spd: 0.9 },
  'Bold': { def: 1.1, atk: 0.9 }, 'Relaxed': { def: 1.1, spe: 0.9 },
  'Impish': { def: 1.1, spa: 0.9 }, 'Lax': { def: 1.1, spd: 0.9 },
  'Timid': { spe: 1.1, atk: 0.9 }, 'Hasty': { spe: 1.1, def: 0.9 },
  'Jolly': { spe: 1.1, spa: 0.9 }, 'Naive': { spe: 1.1, spd: 0.9 },
  'Modest': { spa: 1.1, atk: 0.9 }, 'Mild': { spa: 1.1, def: 0.9 },
  'Quiet': { spa: 1.1, spe: 0.9 }, 'Rash': { spa: 1.1, spd: 0.9 },
  'Calm': { spd: 1.1, atk: 0.9 }, 'Gentle': { spd: 1.1, def: 0.9 },
  'Sassy': { spd: 1.1, spe: 0.9 }, 'Careful': { spd: 1.1, spa: 0.9 },
} as Record<string, Record<string, number>>

function calculateStat(stat: typeof STAT_KEYS[number], baseStat: number, iv: number, ev: number, level: number, nature: string): number {
  const evYield = Math.floor(ev / 4)
  const base = 2 * baseStat + iv + evYield
  if (stat === 'hp') {
    return Math.floor((base * level) / 100) + level + 10
  } else {
    let calc = Math.floor((base * level) / 100) + 5
    const boost = NATURE_BOOSTS[nature]?.[stat] || 1
    return Math.floor(calc * boost)
  }
}

export function IVEVCalculator({ onClose }: Props) {
  const [level, setLevel] = useState(50)
  const [nature, setNature] = useState('Hardy')
  const [ivs, setIVs] = useState<Record<string, number>>({ hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 })
  const [evs, setEVs] = useState<Record<string, number>>({ hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 })

  const [baseStatsInput, setBaseStatsInput] = useState<Record<string, number>>({ hp: 100, atk: 100, def: 100, spa: 100, spd: 100, spe: 100 })

  const calculatedStats = {
    hp: calculateStat('hp', baseStatsInput.hp, ivs.hp, evs.hp, level, nature),
    atk: calculateStat('atk', baseStatsInput.atk, ivs.atk, evs.atk, level, nature),
    def: calculateStat('def', baseStatsInput.def, ivs.def, evs.def, level, nature),
    spa: calculateStat('spa', baseStatsInput.spa, ivs.spa, evs.spa, level, nature),
    spd: calculateStat('spd', baseStatsInput.spd, ivs.spd, evs.spd, level, nature),
    spe: calculateStat('spe', baseStatsInput.spe, ivs.spe, evs.spe, level, nature),
  }

  const totalEV = Object.values(evs).reduce((a, b) => a + b, 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-2xl max-h-96 overflow-y-auto shadow-xl flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700 flex-none">
          <h2 className="text-lg font-bold text-white">IV/EV Calculator</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-4">
            {/* Base Stats */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block font-semibold">Base Stats</label>
              <div className="grid grid-cols-3 gap-2">
                {STAT_KEYS.map((key, idx) => (
                  <div key={key}>
                    <label className="text-[10px] text-slate-500">{STAT_LABELS[idx]}</label>
                    <input
                      type="number"
                      min="0"
                      value={baseStatsInput[key]}
                      onChange={e => setBaseStatsInput({ ...baseStatsInput, [key]: Math.max(0, Number(e.target.value)) })}
                      className="w-full px-2 py-1 rounded text-xs bg-slate-800 border border-slate-700 text-white"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Controls */}
            <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Level</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={level}
                    onChange={e => setLevel(Math.min(100, Math.max(1, Number(e.target.value))))}
                    className="w-full px-2 py-1 rounded text-sm bg-slate-800 border border-slate-700 text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Nature</label>
                  <select
                    value={nature}
                    onChange={e => setNature(e.target.value)}
                    className="w-full px-2 py-1 rounded text-sm bg-slate-800 border border-slate-700 text-white"
                  >
                    {NATURES.map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-2">
                {STAT_KEYS.map((key, idx) => (
                  <div key={key} className="bg-slate-800 rounded p-2">
                    <div className="text-xs font-semibold text-slate-300 mb-1">{STAT_LABELS[idx]}</div>
                    <div className="space-y-1">
                      <div className="text-[11px]">
                        <label className="text-slate-500">IV:</label>
                        <input
                          type="number"
                          min="0"
                          max="31"
                          value={ivs[key]}
                          onChange={e => setIVs({ ...ivs, [key]: Math.min(31, Math.max(0, Number(e.target.value))) })}
                          className="w-full px-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                        />
                      </div>
                      <div className="text-[11px]">
                        <label className="text-slate-500">EV:</label>
                        <input
                          type="number"
                          min="0"
                          max="252"
                          value={evs[key]}
                          onChange={e => setEVs({ ...evs, [key]: Math.min(252, Math.max(0, Number(e.target.value))) })}
                          className="w-full px-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                        />
                      </div>
                      {calculatedStats && (
                        <div className="text-[11px] text-emerald-400 font-semibold">
                          Stat: {calculatedStats[key as typeof STAT_KEYS[number]]}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="text-xs text-slate-400">
                Total EV: {totalEV}/510
                {totalEV > 510 && <span className="text-red-400 ml-2">⚠ Over limit!</span>}
              </div>
            </div>
        </div>
      </div>
    </div>
  )
}
