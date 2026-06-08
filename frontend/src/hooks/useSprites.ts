import { useState, useEffect } from 'react'

const DPE_BASE = '/sprites'

let _manifest: Record<string, string> | null = null
let _promise: Promise<Record<string, string>> | null = null

function fetchManifest(): Promise<Record<string, string>> {
  if (_manifest) return Promise.resolve(_manifest)
  if (_promise) return _promise
  _promise = fetch('/pokemon-icon-manifest.json')
    .then(r => r.json())
    .then(m => { _manifest = m; return m })
    .catch(() => { _manifest = {}; return {} })
  return _promise
}

export function useSpriteManifest() {
  const [manifest, setManifest] = useState<Record<string, string> | null>(_manifest)
  useEffect(() => {
    if (_manifest) { setManifest(_manifest); return }
    fetchManifest().then(setManifest)
  }, [])
  return manifest
}

export function spriteUrl(manifest: Record<string, string> | null, speciesId: number, shiny = false): string | null {
  if (!manifest) return null
  const filename = manifest[String(speciesId)]
  if (!filename) return null
  if (shiny) {
    const shinyFilename = filename.replace('gFrontSprite', 'gFrontSpriteShiny')
    return `${DPE_BASE}/${shinyFilename}`
  }
  return `${DPE_BASE}/${filename}`
}
