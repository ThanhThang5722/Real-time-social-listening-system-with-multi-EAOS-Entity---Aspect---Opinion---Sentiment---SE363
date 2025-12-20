import { useEffect, useState } from 'react';
import { AnalyticsSummary } from '../types';
import { ApiService } from '../services/api';
import { BarChart3, TrendingUp, MessageSquare } from 'lucide-react';
import SentimentChart from './SentimentChart';

export default function EAOSAnalytics() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initial fetch
    fetchSummary();

    // Poll for updates every 10 seconds
    const interval = setInterval(fetchSummary, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchSummary = async () => {
    try {
      const data = await ApiService.getAnalyticsSummary();
      setSummary(data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow-lg p-6 animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded w-5/6"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-6">
        <p className="text-gray-500 text-center">No analytics data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm font-medium">Total Comments</p>
              <p className="text-3xl font-bold mt-2">{summary.total_comments}</p>
            </div>
            <MessageSquare className="w-12 h-12 text-blue-200 opacity-80" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg shadow-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm font-medium">Unique Entities</p>
              <p className="text-3xl font-bold mt-2">{summary.top_entities.length}</p>
            </div>
            <TrendingUp className="w-12 h-12 text-green-200 opacity-80" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg shadow-lg p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm font-medium">Unique Aspects</p>
              <p className="text-3xl font-bold mt-2">{summary.top_aspects.length}</p>
            </div>
            <BarChart3 className="w-12 h-12 text-purple-200 opacity-80" />
          </div>
        </div>
      </div>

      {/* Sentiment Chart */}
      <SentimentChart summary={summary} />

      {/* Top Entities */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5" />
          Top Entities
        </h3>
        <div className="space-y-3">
          {summary.top_entities.slice(0, 8).map((item, idx) => {
            const maxCount = summary.top_entities[0]?.count || 1;
            const percentage = (item.count / maxCount) * 100;

            return (
              <div key={idx} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-700">{item.entity}</span>
                  <span className="text-gray-600">{item.count} mentions</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${percentage}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Top Aspects */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Top Aspects
        </h3>
        <div className="space-y-3">
          {summary.top_aspects.slice(0, 8).map((item, idx) => {
            const maxCount = summary.top_aspects[0]?.count || 1;
            const percentage = (item.count / maxCount) * 100;

            return (
              <div key={idx} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-700">{item.aspect}</span>
                  <span className="text-gray-600">{item.count} mentions</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-purple-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${percentage}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
