export interface TeamInfo {
  id: number;
  name: string | null;
  abbreviation: string | null;
}

export interface Game {
  id: number;
  sport: string;
  status: string;
  game_date: string | null;
  home_team: TeamInfo;
  away_team: TeamInfo;
  home_score: number | null;
  away_score: number | null;
  video_url: string | null;
}

export interface Play {
  id: number;
  period: number;
  clock: string;
  play_type: string;
  description: string;
  home_score: number | null;
  away_score: number | null;
  player: string | null;
}

export interface PlaysResponse {
  total: number;
  plays: Play[];
}

export interface GamesResponse {
  total: number;
  games: Game[];
}

export interface Recap {
  game_id: number;
  content: string | null;
  generated_at?: string;
  status?: string;
  cv_classifications?: number;
}

export interface Highlight {
  timestamp: number;
  play_type: string;
  confidence: number;
}

export interface HighlightsResponse {
  game_id: number;
  video_url: string | null;
  classifications: Highlight[];
}

export interface Standing {
  team_id: number;
  name: string;
  abbreviation: string;
  conference: string;
  wins: number;
  losses: number;
  win_pct: number;
}

export interface RankingsResponse {
  NBA?: Standing[];
  NFL?: Standing[];
}
