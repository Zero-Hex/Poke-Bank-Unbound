import { useState, useEffect } from 'react'
import { getPreferences, setPreferences, type Preferences } from '../api/client'

export function SettingsView() {
  const [prefs, setPrefs] = useState<Preferences | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    getPreferences()
      .then(setPrefs)
      .catch(() => alert('Failed to load preferences'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        Loading preferences...
      </div>
    )
  }

  if (!prefs) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load preferences
      </div>
    )
  }

  async function handleToggle(key: keyof Preferences) {
    if (!prefs) return
    const updated = { ...prefs, [key]: !prefs[key] }
    setPrefs(updated)
    setSaving(true)
    setSaveSuccess(false)
    try {
      await setPreferences({ [key]: updated[key] })
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (err) {
      alert('Failed to save preference: ' + (err as Error).message)
      setPrefs(prefs)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-auto bg-slate-950">
      <div className="px-6 py-4 border-b border-slate-700 flex-none">
        <h1 className="text-lg font-bold text-white">Settings</h1>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="max-w-2xl">
          {/* Display Settings Section */}
          <div className="mb-8">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Display</h2>
            <div className="space-y-3">
              <SettingToggle
                label="List View"
                description="Show Pokémon in list format instead of grid"
                value={prefs.list_view}
                onChange={() => handleToggle('list_view')}
                disabled={saving}
              />
              <SettingToggle
                label="Spoilers"
                description="Show spoiler Pokémon and evolutions"
                value={prefs.spoilers_on}
                onChange={() => handleToggle('spoilers_on')}
                disabled={saving}
              />
              <SettingToggle
                label="Shiny Toggle"
                description="Show shiny indicator overlay on Pokémon"
                value={prefs.shiny_toggle}
                onChange={() => handleToggle('shiny_toggle')}
                disabled={saving}
              />
            </div>
          </div>

          {/* Confirmation Settings Section */}
          <div className="mb-8">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Confirmations</h2>
            <div className="space-y-3">
              <SettingToggle
                label="Confirm Move"
                description='Prompt "Are you sure?" before moving Pokémon'
                value={prefs.confirm_move}
                onChange={() => handleToggle('confirm_move')}
                disabled={saving}
              />
              <SettingToggle
                label="Confirm Release"
                description="Prompt before releasing Pokémon (recommended)"
                value={prefs.confirm_release}
                onChange={() => handleToggle('confirm_release')}
                disabled={saving}
              />
            </div>
          </div>

          {/* Advanced Settings Section */}
          <div className="mb-8">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Advanced</h2>
            <div className="space-y-3">
              <SettingToggle
                label="Show Preset Box"
                description="Display Box 26 (Preset) in the Bank view"
                value={prefs.show_preset_box}
                onChange={() => handleToggle('show_preset_box')}
                disabled={saving}
              />
            </div>
          </div>

          {/* Saved Indicator */}
          {saveSuccess && (
            <div className="px-3 py-2 rounded bg-emerald-900 border border-emerald-700 text-emerald-300 text-sm">
              ✓ Saved
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function SettingToggle({
  label,
  description,
  value,
  onChange,
  disabled,
}: {
  label: string
  description: string
  value: boolean
  onChange: () => void
  disabled: boolean
}) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      className="w-full px-4 py-3 rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-white">{label}</div>
          <div className="text-xs text-slate-400 mt-0.5">{description}</div>
        </div>
        <div
          className={`w-10 h-6 rounded-full transition-colors flex-none ml-4 ${
            value ? 'bg-blue-600' : 'bg-slate-600'
          } flex items-center px-1`}
        >
          <div
            className={`w-4 h-4 rounded-full bg-white transition-transform ${
              value ? 'translate-x-4' : 'translate-x-0'
            }`}
          />
        </div>
      </div>
    </button>
  )
}
