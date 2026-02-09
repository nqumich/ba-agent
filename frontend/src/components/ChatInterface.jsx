import React, { useState, useEffect, useRef } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Paperclip, Mic, ArrowLeft } from "lucide-react";
import { motion } from 'framer-motion';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function ChatInterface({ initialPrompt, onBack }) {
  const [messages, setMessages] = useState(
    initialPrompt ? [{ role: 'user', content: initialPrompt }] : []
  );
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(!!initialPrompt);
  const [conversationId, setConversationId] = useState(null);
  const scrollRef = useRef(null);
  const initialSentRef = useRef(false);

  // 发送消息到后端并更新会话（相对路径 /api 会由 Vite 代理到 localhost:8000）
  const sendToBackend = async (text) => {
    try {
      const url = API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/v1/chat` : '/api/v1/chat';
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId || undefined,
        }),
      });
      const raw = await res.text();
      let data = {};
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch (_) {
        data = {};
      }
      if (!res.ok) {
        const msg = data.detail || data.response || (raw && raw.slice(0, 300)) || res.statusText;
        const statusHint = `(HTTP ${res.status})`;
        throw new Error(`${statusHint} ${typeof msg === 'string' ? msg : JSON.stringify(msg)}`);
      }
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, { role: 'ai', content: data.response ?? '（无回复内容）' }]);
    } catch (err) {
      const isNetwork = err.message.includes('fetch') || err.message.includes('Failed') || err.message.includes('Network');
      const hint = isNetwork || err.message.includes('500') || err.message.includes('502')
        ? '请确认后端已启动：在项目根目录执行 ./venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000'
        : '';
      setMessages(prev => [...prev, {
        role: 'ai',
        content: `请求失败：${err.message}${hint ? ' ' + hint : ''}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  // 进入对话时若有 initialPrompt，则请求首条回复（仅执行一次）
  useEffect(() => {
    if (initialPrompt && !initialSentRef.current) {
      initialSentRef.current = true;
      sendToBackend(initialPrompt);
    }
  }, [initialPrompt]);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text) return;
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setInputValue("");
    setIsLoading(true);
    sendToBackend(text);
  };

  return (
    <div className="flex flex-col h-full bg-white relative">
       {/* Header */}
       <div className="flex items-center px-6 py-4 border-b border-gray-100 bg-white/80 backdrop-blur-md sticky top-0 z-10">
          <Button variant="ghost" size="icon" onClick={onBack} className="mr-2 -ml-2 text-gray-500 hover:text-gray-900">
             <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex flex-col">
             <span className="font-semibold text-gray-900">商业分析助手</span>
             <span className="text-xs text-green-600 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"/> 在线
             </span>
          </div>
       </div>

       {/* Chat Area */}
       <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 scrollbar-hide pb-32" ref={scrollRef}>
          {messages.map((msg, index) => (
            <motion.div 
                key={index} 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start items-start gap-3'}`}
            >
               {msg.role === 'ai' && (
                 <Avatar className="h-8 w-8 mt-1 shrink-0">
                    <AvatarImage src="https://github.com/shadcn.png" />
                    <AvatarFallback>AI</AvatarFallback>
                 </Avatar>
               )}
               
               <div className={`
                  max-w-[85%] sm:max-w-[75%] px-5 py-3 text-sm leading-relaxed shadow-sm
                  ${msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm' 
                    : 'bg-gray-100 text-gray-800 rounded-2xl rounded-tl-sm'}
               `}>
                  {msg.content}
               </div>
            </motion.div>
          ))}
          
          {isLoading && (
             <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-start gap-3"
             >
                <Avatar className="h-8 w-8 mt-1 shrink-0">
                    <AvatarFallback>AI</AvatarFallback>
                </Avatar>
                <div className="bg-gray-50 px-4 py-3 rounded-2xl rounded-tl-sm flex gap-1.5 items-center">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
                </div>
             </motion.div>
          )}
       </div>

       {/* Input Area (Fixed Bottom) */}
       <div className="absolute bottom-0 left-0 right-0 bg-white p-4 border-t border-gray-100">
            <div className="max-w-4xl mx-auto relative">
                <div className="relative flex items-center bg-gray-50 border border-gray-200 rounded-full px-2 py-2 shadow-sm focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-300 transition-all">
                    <Button size="icon" variant="ghost" className="text-gray-400 hover:text-gray-600 h-9 w-9 rounded-full shrink-0">
                        <Paperclip className="h-5 w-5" />
                    </Button>
                    <Input 
                        className="flex-1 border-none bg-transparent shadow-none focus-visible:ring-0 placeholder:text-gray-400 h-10 text-base"
                        placeholder="输入消息..."
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    />
                     <Button size="icon" variant="ghost" className="text-gray-400 hover:text-gray-600 h-9 w-9 rounded-full shrink-0">
                        <Mic className="h-5 w-5" />
                    </Button>
                    <Button 
                        size="icon" 
                        className="bg-blue-600 hover:bg-blue-700 text-white h-9 w-9 rounded-full ml-1 shrink-0 shadow-sm"
                        onClick={handleSend}
                        disabled={!inputValue.trim() || isLoading}
                    >
                        <Send className="h-4 w-4" />
                    </Button>
                </div>
                <div className="text-center mt-2 pb-1">
                     <span className="text-[10px] text-gray-400">AI 生成内容仅供参考</span>
                </div>
            </div>
       </div>
    </div>
  )
}
