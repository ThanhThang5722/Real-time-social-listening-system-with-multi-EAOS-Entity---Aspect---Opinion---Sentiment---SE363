import { useState } from 'react';
import CommentStream from './CommentStream';
import EAOSAnalytics from './EAOSAnalytics';
import Chatbot from './Chatbot';
import { BarChart2, MessageSquare, Bot, Activity } from 'lucide-react';

type TabType = 'stream' | 'analytics' | 'chat';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('stream');

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-md">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 p-2 rounded-lg">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-800">
                  EAOS Dashboard
                </h1>
                <p className="text-sm text-gray-600">
                  Real-time Multi-EAOS Comment Analysis
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="text-right">
                <p className="text-xs text-gray-500">Live Monitoring</p>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-semibold text-gray-700">Active</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="container mx-auto px-4">
          <nav className="flex gap-4">
            <button
              onClick={() => setActiveTab('stream')}
              className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === 'stream'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-600 border-transparent hover:text-blue-600 hover:border-blue-300'
              }`}
            >
              <MessageSquare className="w-5 h-5" />
              Comment Stream
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === 'analytics'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-600 border-transparent hover:text-blue-600 hover:border-blue-300'
              }`}
            >
              <BarChart2 className="w-5 h-5" />
              Analytics
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === 'chat'
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-600 border-transparent hover:text-blue-600 hover:border-blue-300'
              }`}
            >
              <Bot className="w-5 h-5" />
              Chat Assistant
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main View */}
          <div className={`lg:col-span-2 ${activeTab !== 'stream' ? 'hidden lg:block' : ''}`}>
            <div className="h-[calc(100vh-220px)]">
              <CommentStream />
            </div>
          </div>

          {/* Right Column - Analytics or Chat */}
          <div className="lg:col-span-1">
            <div className="space-y-6">
              {activeTab === 'analytics' && (
                <div className="lg:hidden">
                  <EAOSAnalytics />
                </div>
              )}

              {activeTab === 'chat' && (
                <div className="h-[calc(100vh-220px)]">
                  <Chatbot />
                </div>
              )}

              {/* Desktop: Always show analytics sidebar */}
              {activeTab === 'stream' && (
                <div className="hidden lg:block space-y-6">
                  <div className="bg-white rounded-lg shadow-lg p-4">
                    <h3 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
                      <BarChart2 className="w-5 h-5" />
                      Quick Stats
                    </h3>
                    <p className="text-sm text-gray-600">
                      Switch to Analytics tab for detailed insights
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Desktop: Full Analytics View */}
        {activeTab === 'analytics' && (
          <div className="hidden lg:block lg:col-span-3">
            <EAOSAnalytics />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-8">
        <div className="container mx-auto px-4 py-4">
          <div className="text-center text-sm text-gray-600">
            <p>
              EAOS Dashboard - Entity, Aspect, Opinion, Sentiment Analysis System
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Powered by FastAPI + React + WebSocket
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
