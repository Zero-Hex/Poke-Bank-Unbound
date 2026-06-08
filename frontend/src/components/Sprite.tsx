import { useState } from 'react'
import { useSpriteManifest, spriteUrl } from '../hooks/useSprites'

interface Props {
  speciesId: number
  size?: number
  className?: string
  shiny?: boolean
}

export function Sprite({ speciesId, size = 40, className, shiny = false }: Props) {
  const manifest = useSpriteManifest()
  const [shinyFailed, setShinyFailed] = useState(false)

  const effectiveShiny = shiny && !shinyFailed
  const url = spriteUrl(manifest, speciesId, effectiveShiny)

  if (!url) {
    return (
      <div
        style={{ width: size, height: size, opacity: 0.2, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}
      >
        ?
      </div>
    )
  }
  return (
    <img
      src={url}
      width={size}
      height={size}
      className={className}
      alt=""
      style={{ objectFit: 'contain', imageRendering: 'pixelated' }}
      onError={e => {
        if (shiny && !shinyFailed) {
          setShinyFailed(true)
          const fallback = spriteUrl(manifest, speciesId, false)
          if (fallback) (e.target as HTMLImageElement).src = fallback
        } else {
          (e.target as HTMLImageElement).style.opacity = '0'
        }
      }}
    />
  )
}
