import type { SaveData, VaultBox, TradeSecondaryStatus, Pokemon } from '../types/pokemon'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, options)
  const data = await resp.json()
  if (!resp.ok || data.error) throw new Error(data.error || `HTTP ${resp.status}`)
  return data as T
}

// ── Save ──────────────────────────────────────────────────────────────────────

export async function loadSave(file: File): Promise<SaveData> {
  const form = new FormData()
  form.append('save', file)
  const data = await request<{ save: SaveData }>('/api/load', { method: 'POST', body: form })
  return data.save
}

export async function undo(): Promise<SaveData> {
  const data = await request<{ ok: boolean; save: SaveData }>('/api/undo', { method: 'POST' })
  return data.save
}

export async function currentSave(): Promise<SaveData> {
  const data = await request<{ ok: boolean; save: SaveData }>('/api/current_save')
  return data.save
}

export async function downloadSave(): Promise<Blob> {
  const resp = await fetch('/api/download')
  if (!resp.ok) throw new Error('Download failed')
  return resp.blob()
}

// ── Moves ─────────────────────────────────────────────────────────────────────

interface MoveEntry { from: { box: number | string; slot: number }; to: { box: number | string; slot: number } }

export async function movePokemon(moves: MoveEntry[]): Promise<SaveData> {
  const data = await request<{ save: SaveData }>('/api/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ moves }),
  })
  return data.save
}

// ── Sort ──────────────────────────────────────────────────────────────────────

export async function sortPC(sortMode: string, scope: string, currentBox: number, reserveBoxes: number): Promise<SaveData> {
  const data = await request<{ save: SaveData }>('/api/sort', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sort_mode: sortMode, scope, current_box: currentBox, reserve_boxes: reserveBoxes }),
  })
  return data.save
}

// ── Release ───────────────────────────────────────────────────────────────────

export async function releasePokemon(items: { box: number | string; slot: number; vault?: boolean }[]): Promise<SaveData> {
  const data = await request<{ save: SaveData }>('/api/release', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })
  return data.save
}

// ── Vault ─────────────────────────────────────────────────────────────────────

export async function loadVault(): Promise<VaultBox[]> {
  const data = await request<{ cloud: VaultBox[] }>('/api/vault/boxes')
  return data.cloud
}

export async function vaultDeposit(
  fromBox: number | string, fromSlot: number,
  toVaultBox: number, toVaultSlot: number
): Promise<{ save: SaveData; vault: VaultBox[] }> {
  const data = await request<{ save: SaveData; cloud: VaultBox[] }>('/api/vault/deposit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_box: fromBox, from_slot: fromSlot, to_vault_box: toVaultBox, to_vault_slot: toVaultSlot }),
  })
  return { save: data.save, vault: data.cloud }
}

export async function vaultWithdraw(
  fromVaultBox: number, fromVaultSlot: number,
  toBox: number | string, toSlot: number
): Promise<{ save: SaveData; vault: VaultBox[] }> {
  const data = await request<{ save: SaveData; cloud: VaultBox[] }>('/api/vault/withdraw', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_vault_box: fromVaultBox, from_vault_slot: fromVaultSlot, to_box: toBox, to_slot: toSlot }),
  })
  return { save: data.save, vault: data.cloud }
}

export async function vaultMove(
  fromBox: number, fromSlot: number,
  toBox: number, toSlot: number
): Promise<VaultBox[]> {
  const data = await request<{ cloud: VaultBox[] }>('/api/vault/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_box: fromBox, from_slot: fromSlot, to_box: toBox, to_slot: toSlot }),
  })
  return data.cloud
}

export async function vaultBatchDeposit(
  items: Array<{ from_box: number | string; from_slot: number; to_vault_box: number; to_vault_slot: number }>
): Promise<{ save: SaveData; vault: VaultBox[] }> {
  const data = await request<{ save: SaveData; cloud: VaultBox[] }>('/api/vault/batch_deposit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })
  return { save: data.save, vault: data.cloud }
}

export async function vaultBatchMove(moves: Array<{ from_box: number; from_slot: number; to_box: number; to_slot: number }>): Promise<VaultBox[]> {
  const data = await request<{ ok: boolean; cloud: VaultBox[] }>('/api/vault/batch_move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ moves }),
  })
  return data.cloud
}

export async function vaultSort(mode: string, scope: string, box?: number): Promise<VaultBox[]> {
  const data = await request<{ ok: boolean; cloud: VaultBox[] }>('/api/vault/sort', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, scope, box }),
  })
  return data.cloud
}

export async function vaultRename(box: number, name: string): Promise<VaultBox[]> {
  const data = await request<{ cloud: VaultBox[] }>('/api/vault/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ box, name }),
  })
  return data.cloud
}

export async function vaultRelease(items: { vault_box: number; vault_slot: number }[]): Promise<VaultBox[]> {
  const data = await request<{ cloud: VaultBox[] }>('/api/vault/release', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })
  return data.cloud
}

// ── Trade ─────────────────────────────────────────────────────────────────────

export async function tradeSecondaryStatus(): Promise<TradeSecondaryStatus> {
  const data = await request<{ loaded: boolean; trainer?: Trainer_; save?: SaveData; filename?: string }>('/api/trade/secondary_status')
  return {
    loaded: data.loaded,
    save: data.save,
    trainer: data.trainer as unknown as import('../types/pokemon').Trainer,
    filename: data.filename,
  }
}

interface Trainer_ {
  name: string;
  gender: string;
  tid: number;
  playtime: string;
  money: string;
  badges: number;
  boxes?: import('../types/pokemon').Box[];
  party?: (Pokemon | null)[];
}

export async function loadSecondary(file: File): Promise<{ ok: boolean; save: string; trainer: string; filename: string }> {
  const form = new FormData()
  form.append('save', file)
  return request<{ ok: boolean; save: string; trainer: string; filename: string }>('/api/trade/load_secondary', { method: 'POST', body: form })
}

export async function unloadSecondary(): Promise<void> {
  await request('/api/trade/unload_secondary', { method: 'POST' })
}

export type TradeDirection =
  | 'primary_to_secondary'
  | 'primary_to_secondary_vault'
  | 'secondary_to_primary'
  | 'secondary_to_primary_vault'

export async function tradeTransfer(params: {
  direction: TradeDirection;
  from_box: number | string;
  from_slot: number;
  to_box: number | string;
  to_slot: number;
  from_vault?: boolean;
}): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>('/api/trade/transfer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export async function tradeSwap(params: {
  pri_box: number | string;
  pri_slot: number;
  sec_box: number | string;
  sec_slot: number;
  pri_vault?: boolean;
  sec_vault?: boolean;
}): Promise<{ ok: boolean; primary: SaveData; secondary: SaveData }> {
  return request<{ ok: boolean; primary: SaveData; secondary: SaveData }>('/api/trade/swap', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export async function tradeVaultData(): Promise<{ primary: VaultBox[]; secondary: VaultBox[] }> {
  return request<{ ok: boolean; primary: VaultBox[]; secondary: VaultBox[] }>('/api/trade/vault')
}

export async function savePrimary(): Promise<void> {
  await request('/api/trade/save_primary', { method: 'POST' })
}

export async function saveSecondary(): Promise<void> {
  await request('/api/trade/save_secondary', { method: 'POST' })
}

// ── Species / Dex ─────────────────────────────────────────────────────────────

export async function speciesTypes(): Promise<Record<string, string[]>> {
  const resp = await fetch('/species_types.json')
  return resp.json()
}

export async function speciesToNational(): Promise<Record<string, number>> {
  const resp = await fetch('/species_to_national.json')
  return resp.json()
}

export async function speciesList(): Promise<unknown[]> {
  const resp = await fetch('/dex_species.json')
  return resp.json()
}

export async function evoTable(): Promise<Record<string, number[]>> {
  const data = await request<{ ok: boolean; evo_table: Record<string, number[]> }>('/api/evo_table')
  return data.evo_table
}

export interface DexSpeciesEntry { name: string; national: number; borrius: number }

export async function dexSpeciesJson(): Promise<Record<string, DexSpeciesEntry>> {
  const resp = await fetch('/dex_species.json')
  return resp.json()
}

export async function baseStats(): Promise<Record<number, Record<string, number>>> {
  const resp = await fetch('/species_base_stats.json')
  return resp.json()
}

export async function dexFlags(): Promise<{ seen: number[]; caught: number[] }> {
  const data = await request<{ ok: boolean; seen: number[]; caught: number[] }>('/api/dex_flags')
  return { seen: data.seen, caught: data.caught }
}

// ── Bulk move ─────────────────────────────────────────────────────────────────

export async function moveToBox(items: { box: number | string; slot: number }[], targetBox: number): Promise<SaveData> {
  const data = await request<{ ok: boolean; save: SaveData }>('/api/move_to_box', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items, target_box: targetBox }),
  })
  return data.save
}

// ── File downloads ────────────────────────────────────────────────────────────

async function downloadFile(url: string, filename: string): Promise<void> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Download failed: ${resp.status}`)
  const blob = await resp.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export async function exportExcel(): Promise<void> {
  return downloadFile('/api/export_excel', 'pokemon_save.xlsx')
}

export async function exportEvolutions(): Promise<void> {
  return downloadFile('/api/export_evolutions', 'pending_evolutions.xlsx')
}

export async function checkPortaPc(): Promise<boolean> {
  const data = await request<{ ok: boolean; has_porta_pc: boolean }>('/api/has_porta_pc')
  return data.has_porta_pc
}

// ── Recent saves ──────────────────────────────────────────────────────────────

export interface RecentSave { path: string; name: string; trainer: string; tid: number }

export async function recentSaves(): Promise<RecentSave[]> {
  const data = await request<{ ok: boolean; saves: RecentSave[] }>('/api/recent_saves')
  return data.saves
}

export async function loadRecent(path: string): Promise<SaveData> {
  const data = await request<{ ok: boolean; save: SaveData }>('/api/load_recent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  return data.save
}

export interface UpdateInfo {
  current: string
  latest?: string
  up_to_date: boolean
  release_url?: string
  error?: string
}

export async function checkUpdate(): Promise<UpdateInfo> {
  return request<UpdateInfo>('/api/check_update')
}

export interface Preferences {
  list_view: boolean
  spoilers_on: boolean
  shiny_toggle: boolean
  show_preset_box: boolean
  confirm_move: boolean
  confirm_release: boolean
}

export async function getPreferences(): Promise<Preferences> {
  return request<Preferences>('/api/preferences')
}

export async function setPreferences(prefs: Partial<Preferences>): Promise<Preferences> {
  return request<Preferences>('/api/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  })
}
