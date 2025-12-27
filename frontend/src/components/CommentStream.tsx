import { useEffect, useState, useRef } from 'react';
import { Comment } from '../types';
import { MessageCircle, User, RefreshCw, CheckCircle } from 'lucide-react';
import { ApiService } from '../services/api';

const getSentimentColor = (sentiment: string) => {
  switch (sentiment) {
    case 'tích cực':
      return 'bg-green-100 text-green-800 border-green-300';
    case 'tiêu cực':
      return 'bg-red-100 text-red-800 border-red-300';
    case 'trung lập':
      return 'bg-gray-100 text-gray-800 border-gray-300';
    default:
      return 'bg-blue-100 text-blue-800 border-blue-300';
  }
};

export default function CommentStream() {
  const [comments, setComments] = useState<Comment[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [isLoading, setIsLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch ONLY labeled comments from MongoDB (after Airflow batch processing)
  const fetchLabeledComments = async () => {
    try {
      setIsLoading(true);
      const data = await ApiService.getLabeledComments(50, 0);

      if (data.comments && data.comments.length > 0) {
        // Convert MongoDB format to Comment format
        const labeledComments: Comment[] = data.comments.map((c: any) => ({
          id: c._id,
          text: c.text,
          labels: c.labels || [],
          timestamp: c.predicted_at || c.created_at,
          username: `User (${c.source})`
        }));

        // Only show comments that have predictions
        const commentsWithPredictions = labeledComments.filter(c => c.labels && c.labels.length > 0);

        setComments(commentsWithPredictions);
        setLastUpdate(new Date());
      } else {
        setComments([]);
      }

      setIsLoading(false);
    } catch (error) {
      console.error('Failed to fetch labeled comments:', error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch of labeled comments
    fetchLabeledComments();

    // Poll for labeled comments every 30 seconds
    const pollInterval = setInterval(fetchLabeledComments, 30000);

    return () => {
      clearInterval(pollInterval);
    };
  }, []);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
          <MessageCircle className="w-6 h-6" />
          Processed Comments (with Predictions)
        </h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
            <span className="text-xs text-gray-600">
              Auto-refresh every 30s
            </span>
          </div>
          <button
            onClick={fetchLabeledComments}
            disabled={isLoading}
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 transition-colors disabled:opacity-50"
            title="Refresh predictions"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <span className="text-xs text-gray-500">
            {lastUpdate.toLocaleTimeString('vi-VN')}
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-3 scrollbar-thin"
      >
        {isLoading && comments.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <div className="animate-pulse">Loading processed comments...</div>
          </div>
        ) : comments.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p className="mb-2">No processed comments yet.</p>
            <p className="text-sm text-gray-400">
              Submit some comments and wait ~1 minute for batch processing.
            </p>
          </div>
        ) : (
          <>
            <div className="text-sm text-gray-600 mb-2 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span>Showing {comments.length} comments with predictions</span>
            </div>
            {comments.map((comment) => (
              <div
                key={comment.id}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-white"
              >
                <div className="flex items-start gap-3 mb-2">
                  <div className="bg-blue-100 rounded-full p-2">
                    <User className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-800">{comment.username}</span>
                      <span className="text-xs text-gray-500">
                        {new Date(comment.timestamp).toLocaleTimeString('vi-VN')}
                      </span>
                    </div>
                    <p className="text-gray-700 text-sm leading-relaxed">{comment.text}</p>
                  </div>
                </div>

                <div className="mt-3">
                  {comment.labels && comment.labels.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-1 text-xs text-green-600 mb-1">
                        <CheckCircle className="w-3 h-3" />
                        <span className="font-medium">AI Predictions</span>
                      </div>
                      {comment.labels.map((label, idx) => (
                        <div key={idx} className="text-xs bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-3 border border-blue-200">
                          <div className="flex flex-wrap gap-2 mb-2">
                            <span className="font-semibold text-gray-700">Entity:</span>
                            <span className="text-blue-700 font-medium">{label.entity}</span>
                            <span className="text-gray-400">•</span>
                            <span className="font-semibold text-gray-700">Aspect:</span>
                            <span className="text-purple-700 font-medium">{label.aspect}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-gray-700">Opinion:</span>
                            <span className="text-gray-800">{label.opinion}</span>
                            <span className={`ml-auto px-2 py-1 rounded-full text-xs font-semibold border ${getSentimentColor(label.sentiment)}`}>
                              {label.sentiment}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
