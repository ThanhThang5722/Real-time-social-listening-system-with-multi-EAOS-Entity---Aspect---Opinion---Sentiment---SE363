import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { AnalyticsSummary } from '../types';

interface Props {
  summary: AnalyticsSummary;
}

const COLORS = {
  'tích cực': '#22c55e',
  'tiêu cực': '#ef4444',
  'trung lập': '#6b7280',
};

const SENTIMENT_LABELS = {
  'tích cực': 'Positive',
  'tiêu cực': 'Negative',
  'trung lập': 'Neutral',
};

export default function SentimentChart({ summary }: Props) {
  const chartData = Object.entries(summary.sentiment_distribution).map(([sentiment, count]) => ({
    name: SENTIMENT_LABELS[sentiment as keyof typeof SENTIMENT_LABELS] || sentiment,
    value: count,
    sentiment,
  }));

  const total = chartData.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">Sentiment Distribution</h3>

      {total > 0 ? (
        <>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[entry.sentiment as keyof typeof COLORS]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>

          <div className="mt-4 space-y-2">
            {chartData.map((item) => (
              <div key={item.sentiment} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[item.sentiment as keyof typeof COLORS] }}
                  ></div>
                  <span className="text-sm font-medium text-gray-700">{item.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600">{item.value} comments</span>
                  <span className="text-sm font-semibold text-gray-800">
                    {((item.value / total) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="text-center text-gray-500 py-8">
          No data available yet
        </div>
      )}
    </div>
  );
}
