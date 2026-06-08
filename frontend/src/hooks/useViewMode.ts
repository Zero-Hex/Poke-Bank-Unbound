import { useState } from 'react'
import type { ViewMode } from '../types/pokemon'

export function useViewMode(storageKey: string, defaultMode: ViewMode = 'grid'): [ViewMode, (m: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(() => {
    return (localStorage.getItem(storageKey) as ViewMode) || defaultMode
  })
  function setAndStore(m: ViewMode) {
    setMode(m)
    localStorage.setItem(storageKey, m)
  }
  return [mode, setAndStore]
}
