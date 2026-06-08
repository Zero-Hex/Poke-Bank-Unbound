import { useState } from 'react'
import type { BoxSlot, Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'
import { TypeBadge } from './TypeBadge'

interface Props {
  slots: BoxSlot[]
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  onDragStart?: (slot: { box: number | string; slotNum: number; mon: Pokemon }) => void
  onDrop?: (target: { box: number | string; slotNum: number }) => void
  boxId: number | string
  highlightPids?: Set<number>
  multiSelected?: Set<number>
  shinyToggle?: boolean
}

type SortKey = 'name' | 'level' | 'type' | 'nature' | 'ability' | 'box'

export function PokemonBoxList({ slots, selectedPid, onSelect, onDragStart, onDrop, boxId, highlightPids, multiSelected, shinyToggle }: Props) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null)
  const [sortAsc, setSortAsc] = useState(true)

  const filled = slots
    .map((s, i) => ({ s, i }))
    .filter(({ s }) => !s.split && s.mon)

  if (filled.length === 0) {
    return <div className="text-slate-500 text-sm p-4 text-center">No Pokémon in this box</div>
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(true) }
  }

  const rows = [...filled]
  if (sortKey) {
    rows.sort(({ s: a }, { s: b }) => {
      const ma = a.mon!
      const mb = b.mon!
      let va: string | number = 0
      let vb: string | number = 0
      if (sortKey === 'name') { va = ma.nick || ma.name; vb = mb.nick || mb.name }
      else if (sortKey === 'level') { va = ma.level; vb = mb.level }
      else if (sortKey === 'type') { va = (ma.types?.[0] || ''); vb = (mb.types?.[0] || '') }
      else if (sortKey === 'nature') { va = ma.nature; vb = mb.nature }
      else if (sortKey === 'ability') { va = ma.ability; vb = mb.ability }
      else if (sortKey === 'box') { va = typeof ma.box === 'number' ? ma.box : 0; vb = typeof mb.box === 'number' ? mb.box : 0 }
      if (va < vb) return sortAsc ? -1 : 1
      if (va > vb) return sortAsc ? 1 : -1
      return 0
    })
  }

  function ColHeader({ label, k }: { label: string; k: SortKey }) {
    return (
      <th
        className="px-2 py-1 text-left text-xs text-slate-400 cursor-pointer hover:text-white select-none"
        onClick={() => toggleSort(k)}
      >
        {label}{sortKey === k ? (sortAsc ? ' ↑' : ' ↓') : ''}
      </th>
    )
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-slate-900 border-b border-slate-700">
          <tr>
            <th className="px-1 py-1 text-slate-500 text-left w-6">#</th>
            <th className="px-1 py-1 w-8"></th>
            <ColHeader label="Name" k="name" />
            <ColHeader label="Lv" k="level" />
            <ColHeader label="Type" k="type" />
            <ColHeader label="Nature" k="nature" />
            <ColHeader label="Ability" k="ability" />
            <th className="px-2 py-1 text-slate-400 text-xs">HP</th>
            <th className="px-2 py-1 text-slate-400 text-xs">Atk</th>
            <th className="px-2 py-1 text-slate-400 text-xs">Def</th>
            <th className="px-2 py-1 text-slate-400 text-xs">SpA</th>
            <th className="px-2 py-1 text-slate-400 text-xs">SpD</th>
            <th className="px-2 py-1 text-slate-400 text-xs">Spe</th>
            <th className="px-2 py-1 text-slate-400 text-xs" title="EV HP">eHP</th>
            <th className="px-2 py-1 text-slate-400 text-xs" title="EV Atk">eAtk</th>
            <th className="px-2 py-1 text-slate-400 text-xs" title="EV Def">eDef</th>
            <th className="px-2 py-1 text-slate-400 text-xs" title="EV SpA">eSpA</th>
            <th className="px-2 py-1 text-slate-400 text-xs" title="EV SpD">eSpD</th>
            <th className="px-2 py-1 text-slate-400 text-xs" title="EV Spe">eSpe</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ s, i }) => {
            const mon = s.mon!
            const slotNum = i + 1
            const isSelected = selectedPid === mon.pid
            const isHighlighted = highlightPids ? highlightPids.has(mon.pid) : false
            const isMulti = multiSelected ? multiSelected.has(mon.pid) : false

            return (
              <tr
                key={i}
                className={`
                  border-b border-slate-800 cursor-pointer transition-colors
                  ${isSelected ? 'bg-blue-900' : isMulti ? 'bg-purple-900' : isHighlighted ? 'bg-yellow-900/40' : 'hover:bg-slate-800'}
                  ${mon.shiny && shinyToggle ? 'shiny-list-row' : ''}
                `}
                draggable
                onClick={() => onSelect(mon)}
                onDragStart={() => { if (onDragStart) onDragStart({ box: boxId, slotNum, mon }) }}
                onDragOver={e => { if (onDrop) { e.preventDefault(); e.currentTarget.classList.add('outline', 'outline-blue-400') } }}
                onDragLeave={e => { e.currentTarget.classList.remove('outline', 'outline-blue-400') }}
                onDrop={e => {
                  e.preventDefault()
                  e.currentTarget.classList.remove('outline', 'outline-blue-400')
                  if (onDrop) onDrop({ box: boxId, slotNum })
                }}
              >
                <td className="px-1 py-0.5 text-slate-500">{slotNum}</td>
                <td className="px-0.5 py-0.5">
                  <div className="relative">
                    {mon.shiny && <span className="absolute -top-0.5 -left-0.5 text-yellow-400 text-[8px] z-10">★</span>}
                    <Sprite speciesId={mon.species} shiny={mon.shiny} size={28} />
                  </div>
                </td>
                <td className="px-2 py-0.5 text-white font-medium">
                  {mon.nick || mon.name}
                  {mon.nick && mon.nick !== mon.name && <span className="text-slate-400 ml-1">({mon.name})</span>}
                </td>
                <td className="px-2 py-0.5 text-slate-300">{mon.level}</td>
                <td className="px-2 py-0.5">
                  <div className="flex gap-0.5">
                    {mon.types?.map(t => <TypeBadge key={t} type={t} />)}
                  </div>
                </td>
                <td className="px-2 py-0.5 text-slate-300">{mon.nature}</td>
                <td className="px-2 py-0.5 text-slate-300">{mon.ability}</td>
                {(['hp','atk','def','spa','spd','spe'] as const).map(stat => (
                  <td key={stat} className={`px-2 py-0.5 text-center ${mon.ivs[stat] === 31 ? 'text-emerald-400 font-bold' : 'text-slate-300'}`}>
                    {mon.ivs[stat]}
                  </td>
                ))}
                {(['hp','atk','def','spa','spd','spe'] as const).map(stat => (
                  <td key={`ev_${stat}`} className={`px-2 py-0.5 text-center ${mon.evs?.[stat] ? 'text-amber-400' : 'text-slate-600'}`}>
                    {mon.evs?.[stat] ?? 0}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
