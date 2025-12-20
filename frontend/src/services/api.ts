import { AnalyticsSummary, ChatMessage } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api';

export class ApiService {
  static async getAnalyticsSummary(): Promise<AnalyticsSummary> {
    const response = await fetch(`${API_BASE_URL}/analytics/summary`);
    if (!response.ok) throw new Error('Failed to fetch analytics summary');
    return response.json();
  }

  static async sendChatMessage(message: string): Promise<ChatMessage> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });
    if (!response.ok) throw new Error('Failed to send chat message');
    return response.json();
  }

  static async searchComments(query: string, limit = 20) {
    const response = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    if (!response.ok) throw new Error('Failed to search comments');
    return response.json();
  }

  static connectCommentStream(): WebSocket {
    return new WebSocket(`${WS_BASE_URL}/ws/comments`);
  }

  static connectAnalyticsStream(): WebSocket {
    return new WebSocket(`${WS_BASE_URL}/ws/analytics`);
  }
}
