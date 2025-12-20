import { useEffect, useState, useRef } from 'react';
import { Comment, WebSocketMessage } from '../types';
import { MessageCircle, User } from 'lucide-react';

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
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket('ws://localhost:8000/api/ws/comments');
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('Connected to comment stream');
    };

    ws.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      if (message.type === 'comment') {
        const comment = message.data as Comment;
        setComments((prev) => [comment, ...prev].slice(0, 50)); // Keep last 50 comments
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('Disconnected from comment stream');
    };

    return () => {
      ws.close();
    };
  }, []);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
          <MessageCircle className="w-6 h-6" />
          Live Comment Stream
        </h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="text-sm text-gray-600">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-3 scrollbar-thin"
      >
        {comments.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            Waiting for comments...
          </div>
        )}

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

            <div className="mt-3 space-y-2">
              {comment.labels.map((label, idx) => (
                <div key={idx} className="text-xs bg-gray-50 rounded p-2 border border-gray-200">
                  <div className="flex flex-wrap gap-2">
                    <span className="font-semibold text-gray-600">Entity:</span>
                    <span className="text-blue-600">{label.entity}</span>
                    <span className="text-gray-400">|</span>
                    <span className="font-semibold text-gray-600">Aspect:</span>
                    <span className="text-purple-600">{label.aspect}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="font-semibold text-gray-600">Opinion:</span>
                    <span className="text-gray-700">{label.opinion}</span>
                    <span className={`ml-auto px-2 py-0.5 rounded-full text-xs font-medium border ${getSentimentColor(label.sentiment)}`}>
                      {label.sentiment}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
