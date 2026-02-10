import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { 
  Plus, Search, ChevronDown, 
  Settings, LogOut, MessageSquare
} from "lucide-react";

export function Sidebar({ onNewChat, history = [], onSelectHistory, currentSessionId }) {
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // 根据搜索词过滤历史记录
  const filteredHistory = history.filter(item => 
    item.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="w-64 h-screen bg-[#F7F8FA] flex flex-col border-r border-gray-100 flex-shrink-0 font-sans text-sm">
      {/* Header */}
      <div className="p-4 pb-2">
        <h1 className="text-lg font-bold text-gray-800 mb-4 px-2">商业分析助手</h1>
        <Button 
          className="w-full justify-start bg-blue-50 text-blue-600 hover:bg-blue-100 border-none rounded-lg h-9 mb-3 shadow-none"
          onClick={onNewChat}
        >
          <Plus className="mr-2 h-4 w-4" />
          新建任务
        </Button>

        <div className="relative mb-2">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
          <Input 
            placeholder="搜索任务" 
            className="pl-9 h-9 bg-transparent border-none shadow-none focus-visible:ring-0 placeholder:text-gray-400 hover:bg-gray-100 transition-colors rounded-lg" 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <ScrollArea className="flex-1 px-3">
        {/* 历史任务列表 */}
        <div 
          className="mt-2 mb-2 px-2 flex items-center justify-between text-xs text-gray-500 font-medium cursor-pointer hover:text-gray-700 transition-colors select-none group"
          onClick={() => setIsHistoryOpen(!isHistoryOpen)}
        >
          <span>历史任务</span>
          <ChevronDown className={`h-3 w-3 transition-transform duration-200 text-gray-400 group-hover:text-gray-600 ${isHistoryOpen ? '' : '-rotate-90'}`} />
        </div>
        
        {isHistoryOpen && (
          <div className="space-y-0.5 animate-in slide-in-from-top-1 fade-in duration-200">
            {filteredHistory.length > 0 ? (
              filteredHistory.map((item) => (
                <Button 
                  key={item.id} 
                  variant="ghost" 
                  onClick={() => onSelectHistory(item.id)}
                  className={`w-full justify-start h-8 font-normal hover:bg-gray-200/50 text-xs truncate block text-left ${
                    currentSessionId === item.id ? 'bg-gray-200/60 text-gray-900 font-medium' : 'text-gray-600'
                  }`}
                  title={item.title}
                >
                  <span className="flex items-center gap-2 truncate w-full">
                    <MessageSquare className="w-3 h-3 flex-shrink-0 opacity-70" />
                    <span className="truncate">{item.title}</span>
                  </span>
                </Button>
              ))
            ) : (
                <div className="px-2 py-4 text-center text-xs text-gray-400">
                    {searchQuery ? "未找到相关任务" : "暂无历史记录"}
                </div>
            )}
          </div>
        )}
      </ScrollArea>

      {/* Footer */}
      <div className="p-3 mt-auto border-t border-gray-200">
        <Button variant="ghost" className="w-full justify-start h-12 px-2 hover:bg-gray-200/50">
          <Avatar className="h-8 w-8 mr-2">
            <AvatarImage src="https://github.com/shadcn.png" />
            <AvatarFallback>U</AvatarFallback>
          </Avatar>
          <div className="flex flex-col items-start text-xs">
            <span className="font-medium text-gray-700">叶子钰</span>
          </div>
          <div className="ml-auto flex gap-1">
             <Settings className="h-4 w-4 text-gray-400" />
             <LogOut className="h-4 w-4 text-gray-400" />
          </div>
        </Button>
      </div>
    </div>
  );
}
