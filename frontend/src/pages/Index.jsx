import React, { useState } from 'react';
import { Sidebar } from "@/components/Sidebar";
import { ChatInputArea } from "@/components/ChatInputArea";
import { FeatureCards } from "@/components/FeatureCards";
import { ShowcaseGallery } from "@/components/ShowcaseGallery";
import { ChatInterface } from "@/components/ChatInterface";

const Index = () => {
  const [showShowcase, setShowShowcase] = useState(false);
  const [chatState, setChatState] = useState({
    active: false,
    initialPrompt: ''
  });

  const handleStartChat = (prompt) => {
    setChatState({
      active: true,
      initialPrompt: prompt
    });
  };

  const handleBackToHome = () => {
    setChatState({
      active: false,
      initialPrompt: ''
    });
  };

  return (
    <div className="flex min-h-screen bg-white overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col h-screen relative overflow-hidden">
        
        {/* Chat Interface Mode */}
        {chatState.active ? (
            <ChatInterface 
                initialPrompt={chatState.initialPrompt} 
                onBack={handleBackToHome}
            />
        ) : (
            /* Landing Page Mode */
            <>
                {/* Background decorative elements */}
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
                    <div className="flex flex-col min-h-full justify-center pb-12 pt-20">
                        <ChatInputArea onSend={handleStartChat} />
                        <div className="mt-auto">
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
