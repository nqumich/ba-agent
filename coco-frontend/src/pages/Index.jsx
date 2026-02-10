import React, { useState } from 'react';
import { Sidebar } from "@/components/Sidebar";
import { ChatInputArea } from "@/components/ChatInputArea";
import { FeatureCards } from "@/components/FeatureCards";
import { ShowcaseGallery } from "@/components/ShowcaseGallery";
import { ChatInterface } from "@/components/ChatInterface";

const Index = () => {
  const [showShowcase, setShowShowcase] = useState(false);
  
  // 初始历史记录数据
  const initialHistory = [
    { id: 'h1', title: "生成统计图,统计每个数据周...", messages: [{role: 'user', content: '生成统计图,统计每个数据周的数据变化'}, {role: 'ai', content: '好的，已为您生成统计图。'}] },
    { id: 'h2', title: "帮我生成折线图,两个纵坐标...", messages: [{role: 'user', content: '帮我生成折线图,两个纵坐标'}, {role: 'ai', content: '收到，正在处理数据...'}] },
    { id: 'h3', title: "生成饼图,展示各平台...", messages: [{role: 'user', content: '生成饼图,展示各平台占比'}, {role: 'ai', content: '饼图已生成，请查看。'}] },
    { id: 'h4', title: "近三天小红书的热搜词top5...", messages: [{role: 'user', content: '近三天小红书的热搜词top5'}, {role: 'ai', content: 'Top 5 热搜词如下：...'}] },
  ];

  const [history, setHistory] = useState(initialHistory);
  const [currentSessionId, setCurrentSessionId] = useState(null);

  // 开始新对话：创建新 Session 并设为当前
  const handleStartChat = (prompt) => {
    const newSessionId = `session-${Date.now()}`;
    const newSession = {
        id: newSessionId,
        title: prompt, // 使用 Prompt 作为标题
        messages: [{ role: 'user', content: prompt }],
        createdAt: new Date()
    };
    
    // 添加到历史记录最前面
    setHistory(prev => [newSession, ...prev]);
    setCurrentSessionId(newSessionId);
  };

  // 切换历史会话
  const handleSelectHistory = (sessionId) => {
    setCurrentSessionId(sessionId);
  };

  // 更新当前会话的消息
  const handleUpdateSessionMessages = (newMessages) => {
    setHistory(prev => prev.map(session => 
        session.id === currentSessionId 
            ? { ...session, messages: newMessages }
            : session
    ));
  };

  // 返回首页（不清除历史，只是取消当前选中状态）
  const handleBackToHome = () => {
    setCurrentSessionId(null);
  };

  // 获取当前激活的会话对象
  const currentSession = history.find(h => h.id === currentSessionId);

  return (
    <div className="flex min-h-screen bg-white overflow-hidden">
      <Sidebar 
        onNewChat={handleBackToHome} 
        history={history}
        onSelectHistory={handleSelectHistory}
        currentSessionId={currentSessionId}
      />
      <main className="flex-1 flex flex-col h-screen relative overflow-hidden">
        
        {/* Chat Interface Mode */}
        {currentSessionId && currentSession ? (
            <ChatInterface 
                key={currentSessionId} // 确保切换会话时组件重置
                initialMessages={currentSession.messages} 
                onUpdateMessages={handleUpdateSessionMessages}
                onBack={handleBackToHome}
            />
        ) : (
            /* Landing Page Mode */
            <>{/* Background decorative elements */}
                <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-0">
                    <div className="absolute top-[10%] left-[20%] w-64 h-64 bg-blue-50/50 rounded-full blur-[100px]" />
                    <div className="absolute bottom-[10%] right-[20%] w-72 h-72 bg-purple-50/50 rounded-full blur-[100px]" />
                </div>

                {/* Main Content (Chat & Features) */}
                <div
                className={`flex-1 overflow-y-auto z-10 scrollbar-hide transition-all duration-500 ease-in-out transform ${
                    showShowcase ? '-translate-y-full opacity-0' : 'translate-y-0 opacity-100'
                }`}
                >
                    <div className="flex flex-col min-h-full">
                        
                        {/* 核心区域：BA Agent 标题、输入框、灵感库 */}
                        <div className="flex-1 flex flex-col justify-end items-center w-full pb-2">
                            <ChatInputArea onSend={handleStartChat} />
                        </div>
                        
                        {/* 底部区域：精选案例 */}
                        <div className="w-full flex-none pb-2">
                            <FeatureCards onMoreClick={() => setShowShowcase(true)} />
                        </div>
                    </div>
                </div>

                {/* Showcase Gallery Overlay (Slide Up) */}
                <div 
                    className={`absolute inset-0 z-20 bg-white transition-transform duration-500 ease-in-out ${
                        showShowcase ? 'translate-y-0' : 'translate-y-full'
                    }`}
                >
                    <ShowcaseGallery onClose={() => setShowShowcase(false)} />
                </div>
            </>
        )}
      </main>
    </div>
  );
};

export default Index;
