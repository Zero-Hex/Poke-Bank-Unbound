export interface IVs {
  hp: number; atk: number; def: number;
  spe: number; spa: number; spd: number;
}

export interface EVs {
  hp: number; atk: number; def: number;
  spe: number; spa: number; spd: number;
}

export interface Pokemon {
  pid: number;
  species: number;
  name: string;
  nick: string;
  level: number;
  nature: string;
  ability: string;
  item: string | null;
  gender: string;
  shiny: boolean;
  ivs: IVs;
  evs?: EVs;
  moves: string[];
  exp: number;
  box: number | 'party';
  slot: number;
  national?: number;
  national_dex?: number;
  borrius?: number;
  types?: string[];
  vault_from_trainer?: string;
  vault_from_tid?: number;
  raw?: number[];
}

export interface BoxSlot {
  mon: Pokemon | null;
  split?: boolean;
}

export interface Box {
  box: number;
  name: string;
  slots: BoxSlot[];
}

export interface Trainer {
  name: string;
  gender: string;
  tid: number;
  playtime: string;
  money: string;
  badges: number;
}

export interface SaveData {
  trainer: Trainer;
  party: (Pokemon | null)[];
  boxes: Box[];
}

export interface VaultSlot {
  mon: (Pokemon & { raw?: number[] }) | null;
}

export interface VaultBox {
  box: number;
  name: string;
  slots: VaultSlot[];
}

export type ViewMode = 'grid' | 'list' | 'compact';
export type NavTab = 'bank' | 'dex' | 'vault' | 'trade' | 'settings';

export interface TradeSecondaryStatus {
  loaded: boolean;
  save?: SaveData;
  trainer?: Trainer;
  filename?: string;
}
