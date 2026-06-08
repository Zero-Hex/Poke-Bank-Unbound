import type { Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'
import { TypeBadge } from './TypeBadge'

interface Props {
  mon: Pokemon | null
  onClose?: () => void
  evoFull?: Record<string, { target_id: number; target?: string; desc?: string }[]>
  baseStatsData?: Record<number, Record<string, number>>
}

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

function calculateStat(stat: 'hp' | 'atk' | 'def' | 'spa' | 'spd' | 'spe', baseStat: number, iv: number, ev: number, level: number, nature: string): number {
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

export function DetailPanel({ mon, onClose, evoFull, baseStatsData }: Props) {
  if (!mon) {
    return (
      <div className="w-56 flex-none flex flex-col items-center justify-center bg-slate-900 border-l border-slate-700 text-slate-500 text-sm text-center p-4">
        Click a Pokémon<br />to see details
      </div>
    )
  }

  const location = mon.box === 'party' ? 'Party' : `Box ${mon.box}`

  return (
    <div className="w-56 flex-none flex flex-col bg-slate-900 border-l border-slate-700 overflow-y-auto">
      {onClose && (
        <button
          className="absolute top-2 right-2 text-slate-400 hover:text-white text-lg leading-none z-10"
          onClick={onClose}
        >
          ×
        </button>
      )}

      {/* Header */}
      <div className="flex flex-col items-center pt-4 pb-2 px-3 border-b border-slate-700">
        <Sprite speciesId={mon.species} shiny={mon.shiny} size={80} />
        <div className="text-white font-bold text-base mt-1">
          {mon.shiny ? '★ ' : ''}{mon.name}
        </div>
        {mon.nick && mon.nick !== mon.name && (
          <div className="text-slate-400 text-xs">"{mon.nick}"</div>
        )}
        <div className="text-slate-400 text-xs mt-0.5">{mon.gender} · Lv.{mon.level}</div>
        {mon.types && mon.types.length > 0 && (
          <div className="flex gap-1 mt-1.5">
            {mon.types.map(t => <TypeBadge key={t} type={t} />)}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="px-3 py-2 border-b border-slate-700">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Info</div>
        <InfoRow label="Nature" value={mon.nature} />
        <InfoRow label="Ability" value={mon.ability} />
        {mon.item && <InfoRow label="Item" value={mon.item} />}
        <InfoRow label="Location" value={`${location} · Slot ${mon.slot}`} muted />
        {mon.vault_from_trainer && (
          <InfoRow label="OT" value={`${mon.vault_from_trainer} #${mon.vault_from_tid}`} muted />
        )}
      </div>

      {/* Evolution */}
      {evoFull && evoFull[String(mon.species)] && evoFull[String(mon.species)].length > 0 && (
        <div className="px-3 py-2 border-b border-slate-700">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Evolution</div>
          {evoFull[String(mon.species)].map((evo, idx) => (
            <div key={idx} className="text-[10px] text-slate-300 mb-1">
              <div className="font-medium text-purple-300">{evo.target}</div>
              <div className="text-slate-400 text-[9px]">{evo.desc}</div>
            </div>
          ))}
        </div>
      )}

      {/* Calculated Stats */}
      {baseStatsData && baseStatsData[mon.species] && (
        <div className="px-3 py-2 border-b border-slate-700">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Stats</div>
          {STAT_KEYS.map((key, idx) => {
            const baseStat = baseStatsData[mon.species][key]
            const iv = mon.ivs[key]
            const ev = mon.evs?.[key] ?? 0
            const stat = calculateStat(key, baseStat, iv, ev, mon.level, mon.nature)
            return (
              <div key={key} className="flex items-center justify-between mb-0.5">
                <span className="text-[10px] text-slate-400 flex-none">{STAT_LABELS[idx]}</span>
                <span className="text-[10px] text-slate-300 font-medium">{stat}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* IVs */}
      <div className="px-3 py-2 border-b border-slate-700">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">IVs</div>
        {STAT_KEYS.map((key, idx) => {
          const v = mon.ivs[key]
          const pct = Math.round(v / 31 * 100)
          return (
            <div key={key} className="flex items-center gap-1 mb-0.5">
              <span className="text-[10px] text-slate-400 w-7 flex-none">{STAT_LABELS[idx]}</span>
              <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${v === 31 ? 'bg-emerald-400' : 'bg-blue-500'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={`text-[10px] w-5 text-right ${v === 31 ? 'text-emerald-400 font-bold' : 'text-slate-300'}`}>{v}</span>
            </div>
          )
        })}
      </div>

      {/* EVs */}
      {mon.evs && (
        <div className="px-3 py-2 border-b border-slate-700">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">EVs</div>
          {STAT_KEYS.map((key, idx) => {
            const v = mon.evs![key] ?? 0
            const pct = Math.round(v / 252 * 100)
            return (
              <div key={key} className="flex items-center gap-1 mb-0.5">
                <span className="text-[10px] text-slate-400 w-7 flex-none">{STAT_LABELS[idx]}</span>
                <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${v === 252 ? 'bg-amber-400' : 'bg-amber-600'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className={`text-[10px] w-6 text-right ${v > 0 ? 'text-amber-400' : 'text-slate-600'}`}>{v}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Moves */}
      <div className="px-3 py-2">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Moves</div>
        <div className="grid grid-cols-2 gap-0.5">
          {mon.moves.map((m, i) => (
            <div key={i} className={`text-[10px] px-1.5 py-0.5 rounded ${m ? 'bg-slate-700 text-slate-200' : 'bg-slate-800 text-slate-600'}`}>
              {m || '—'}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex justify-between items-baseline gap-1 mb-0.5">
      <span className="text-[10px] text-slate-500 flex-none">{label}</span>
      <span className={`text-[10px] text-right truncate ${muted ? 'text-slate-500' : 'text-slate-200'}`}>{value}</span>
    </div>
  )
}
