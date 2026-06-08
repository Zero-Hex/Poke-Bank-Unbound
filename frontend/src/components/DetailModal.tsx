import type { Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'
import { TypeBadge } from './TypeBadge'

interface Props {
  mon: Pokemon | null
  onClose: () => void
}

const STAT_KEYS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'] as const
const STAT_LABELS = ['HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe']

export function DetailModal({ mon, onClose }: Props) {
  if (!mon) return null

  const location = mon.box === 'party' ? 'Party' : `Box ${mon.box}`

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-slate-800 border border-slate-600 rounded-xl shadow-2xl w-80 max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start gap-3 p-4 border-b border-slate-700">
          <Sprite speciesId={mon.species} shiny={mon.shiny} size={80} />
          <div className="flex-1 min-w-0">
            <div className="text-white font-bold text-lg leading-tight">
              {mon.shiny ? '★ ' : ''}{mon.name}
            </div>
            {mon.nick && mon.nick !== mon.name && (
              <div className="text-slate-400 text-xs">"{mon.nick}"</div>
            )}
            <div className="text-slate-400 text-sm">{mon.gender} · Lv.{mon.level}</div>
            {mon.types && mon.types.length > 0 && (
              <div className="flex gap-1 mt-1">
                {mon.types.map(t => <TypeBadge key={t} type={t} />)}
              </div>
            )}
          </div>
          <button
            className="text-slate-400 hover:text-white text-xl leading-none flex-none"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Info */}
          <section>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Info</div>
            <InfoRow label="Nature" value={mon.nature} />
            <InfoRow label="Ability" value={mon.ability} />
            {mon.item && <InfoRow label="Item" value={mon.item} />}
            <InfoRow label="Location" value={`${location} · Slot ${mon.slot}`} muted />
            {mon.vault_from_trainer && (
              <InfoRow label="OT" value={`${mon.vault_from_trainer} #${mon.vault_from_tid}`} muted />
            )}
          </section>

          {/* IVs */}
          <section>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">IVs</div>
            {STAT_KEYS.map((key, idx) => {
              const v = mon.ivs[key]
              const pct = Math.round(v / 31 * 100)
              return (
                <div key={key} className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-slate-400 w-8 flex-none">{STAT_LABELS[idx]}</span>
                  <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${v === 31 ? 'bg-emerald-400' : 'bg-blue-500'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className={`text-xs w-6 text-right ${v === 31 ? 'text-emerald-400 font-bold' : 'text-slate-300'}`}>{v}</span>
                </div>
              )
            })}
          </section>

          {/* EVs */}
          {mon.evs && (
            <section>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">EVs</div>
              {STAT_KEYS.map((key, idx) => {
                const v = mon.evs![key] ?? 0
                const pct = Math.round(v / 252 * 100)
                return (
                  <div key={key} className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-slate-400 w-8 flex-none">{STAT_LABELS[idx]}</span>
                    <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${v === 252 ? 'bg-amber-400' : 'bg-amber-600'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className={`text-xs w-6 text-right ${v > 0 ? 'text-amber-400' : 'text-slate-600'}`}>{v}</span>
                  </div>
                )
              })}
            </section>
          )}

          {/* Moves */}
          <section>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Moves</div>
            <div className="grid grid-cols-2 gap-1">
              {mon.moves.map((m, i) => (
                <div key={i} className={`text-xs px-2 py-1 rounded ${m ? 'bg-slate-700 text-slate-200' : 'bg-slate-800/50 text-slate-600'}`}>
                  {m || '—'}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex justify-between gap-2 mb-1">
      <span className="text-xs text-slate-400 flex-none">{label}</span>
      <span className={`text-xs text-right truncate ${muted ? 'text-slate-500' : 'text-white'}`}>{value}</span>
    </div>
  )
}
