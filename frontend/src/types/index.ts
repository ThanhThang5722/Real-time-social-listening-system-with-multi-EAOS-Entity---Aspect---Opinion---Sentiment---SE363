export interface EAOSLabel {
  entity: string;
  aspect: string;
  opinion: string;
  sentiment: string;
}

export interface Comment {
  id: string;
  text: string;
  labels: EAOSLabel[];
  timestamp: string;
  username: string;
}

export interface AnalyticsSummary {
  total_comments: number;
  sentiment_distribution: Record<string, number>;
  top_entities: Array<{ entity: string; count: number }>;
  top_aspects: Array<{ aspect: string; count: number }>;
  recent_comments: Comment[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface WebSocketMessage {
  type: 'comment' | 'analytics';
  data: Comment | AnalyticsSummary;
}
