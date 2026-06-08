import { useState, useMemo } from 'react'
import type { Box, Pokemon } from '../types/pokemon'
import { Sprite } from './Sprite'
import { TypeBadge } from './TypeBadge'

interface Props {
  boxes: Box[]
  selectedPid?: number | null
  onSelect: (mon: Pokemon) => void
  multiSelected?: Set<number>
  selectColor?: 'move' | 'release'
}

type SortKey = 'name' | 'level' | 'type' | 'nature' | 'ability' | 'box'

interface MonEntry {
  mon: Pokemon
  box: number
  slot: number
}

const LS_SORT_KEY = 'ub_listSortKey'
const LS_SORT_ASC = 'ub_listSortAsc'

export function ListView({ boxes, selectedPid, onSelect, multiSelected, selectColor }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>(() =>
    (localStorage.getItem(LS_SORT_KEY) as SortKey) || 'box'
  )
  const [sortAsc, setSortAsc] = useState<boolean>(() =>
    localStorage.getItem(LS_SORT_ASC) !== 'false'
  )

  const allMons = useMemo<MonEntry[]>(() => {
    const result: MonEntry[] = []
    for (const box of boxes) {
      for (let i = 0; i < box.slots.length; i++) {
        const s = box.slots[i]
        if (!s.split && s.mon) {
          result.push({ mon: s.mon, box: box.box, slot: i + 1 })
        }
      }
    }
    return result
  }, [boxes])

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      const next = !sortAsc
      setSortAsc(next)
      localStorage.setItem(LS_SORT_ASC, String(next))
    } else {
      setSortKey(key)
      localStorage.setItem(LS_SORT_KEY, key)
      setSortAsc(true)
      localStorage.setItem(LS_SORT_ASC, 'true')
    }
  }

  const sorted = useMemo(() => [...allMons].sort((a, b) => {
    let va: string | number = 0
    let vb: string | number = 0
    if (sortKey === 'name') { va = a.mon.nick || a.mon.name; vb = b.mon.nick || b.mon.name }
    else if (sortKey === 'level') { va = a.mon.level; vb = b.mon.level }
    else if (sortKey === 'type') { va = a.mon.types?.[0] || ''; vb = b.mon.types?.[0] || '' }
    else if (sortKey === 'nature') { va = a.mon.nature; vb = b.mon.nature }
    else if (sortKey === 'ability') { va = a.mon.ability; vb = b.mon.ability }
    else if (sortKey === 'box') {
      if (a.box !== b.box) return sortAsc ? a.box - b.box : b.box - a.box
      return sortAsc ? a.slot - b.slot : b.slot - a.slot
    }
    if (va < vb) return sortAsc ? -1 : 1
    if (va > vb) return sortAsc ? 1 : -1
    return 0
  }), [allMons, sortKey, sortAsc])

  if (sorted.length === 0) {
    return <div className="text-slate-500 text-sm p-8 text-center">No Pokémon found</div>
  }

  function SortTh({ label, k }: { label: string; k: SortKey }) {
    return (
      <th
        className="px-2 py-1.5 text-left text-xs text-slate-400 cursor-pointer hover:text-white select-none whitespace-nowrap"
        onClick={() => toggleSort(k)}
      >
        {label}{sortKey === k ? (sortAsc ? ' ↑' : ' ↓') : ''}
      </th>
    )
  }

  return (
    <div className="overflow-auto flex-1">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-slate-900 border-b border-slate-700 z-10">
          <tr>
            <SortTh label="Box" k="box" />
            <th className="px-1 py-1.5 w-8"></th>
            <SortTh label="Name" k="name" />
            <SortTh label="Lv" k="level" />
            <SortTh label="Type" k="type" />
            <SortTh label="Nature" k="nature" />
            <SortTh label="Ability" k="ability" />
            <th className="px-1.5 py-1.5 text-slate-400 text-xs">HP</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs">Atk</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs">Def</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs">SpA</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs">SpD</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs">Spe</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs" title="EV HP">eHP</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs" title="EV Atk">eAtk</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs" title="EV Def">eDef</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs" title="EV SpA">eSpA</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs" title="EV SpD">eSpD</th>
            <th className="px-1.5 py-1.5 text-slate-400 text-xs" title="EV Spe">eSpe</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ mon, box, slot }) => {
            const isSelected = selectedPid === mon.pid
            const isMulti = multiSelected ? multiSelected.has(mon.pid) : false
            return (
              <tr
                key={`${box}-${slot}`}
                className={`
                  border-b border-slate-800 cursor-pointer transition-colors
                  ${isSelected ? 'bg-blue-900' : isMulti ? (selectColor === 'release' ? 'bg-red-900' : 'bg-blue-900') : 'hover:bg-slate-800'}
                  ${mon.shiny && !isSelected && !isMulti ? 'shiny-list-row' : ''}
                `}
                onClick={() => onSelect(mon)}
              >
                <td className="px-2 py-0.5 text-slate-500 whitespace-nowrap">{box}·{slot}</td>
                <td className="px-0.5 py-0.5">
                  <div className="relative">
                    {mon.shiny && <span className="absolute -top-0.5 -left-0.5 text-yellow-400 text-[8px] z-10">★</span>}
                    <Sprite speciesId={mon.species} shiny={mon.shiny} size={28} />
                  </div>
                </td>
                <td className="px-2 py-0.5 text-white font-medium whitespace-nowrap">
                  {mon.nick || mon.name}
                  {mon.nick && mon.nick !== mon.name && <span className="text-slate-400 ml-1">({mon.name})</span>}
                </td>
                <td className="px-2 py-0.5 text-slate-300">{mon.level}</td>
                <td className="px-2 py-0.5">
                  <div className="flex gap-0.5">
                    {mon.types?.map(t => <TypeBadge key={t} type={t} />)}
                  </div>
                </td>
                <td className="px-2 py-0.5 text-slate-300 whitespace-nowrap">{mon.nature}</td>
                <td className="px-2 py-0.5 text-slate-300 whitespace-nowrap">{mon.ability}</td>
                {(['hp','atk','def','spa','spd','spe'] as const).map(stat => (
                  <td key={stat} className={`px-1.5 py-0.5 text-center ${mon.ivs[stat] === 31 ? 'text-emerald-400 font-bold' : 'text-slate-300'}`}>
                    {mon.ivs[stat]}
                  </td>
                ))}
                {(['hp','atk','def','spa','spd','spe'] as const).map(stat => (
                  <td key={`ev_${stat}`} className={`px-1.5 py-0.5 text-center ${mon.evs?.[stat] ? 'text-amber-400' : 'text-slate-600'}`}>
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
