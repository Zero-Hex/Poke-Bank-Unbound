const TYPE_COLORS: Record<string, string> = {
  normal: '#A8A878', fire: '#F08030', water: '#6890F0', electric: '#F8D030',
  grass: '#78C850', ice: '#98D8D8', fighting: '#C03028', poison: '#A040A0',
  ground: '#E0C068', flying: '#A890F0', psychic: '#F85888', bug: '#A8B820',
  rock: '#B8A038', ghost: '#705898', dragon: '#7038F8', dark: '#705848',
  steel: '#B8B8D0', fairy: '#EE99AC',
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

interface Props {
  type: string
  className?: string
}

export function TypeBadge({ type, className = '' }: Props) {
  const color = TYPE_COLORS[type.toLowerCase()] || '#888'
  const textColor = isLightColor(color) ? '#1e293b' : '#ffffff'
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold leading-none ${className}`}
      style={{ background: color, color: textColor }}
    >
      {type}
    </span>
  )
}

export { TYPE_COLORS }
