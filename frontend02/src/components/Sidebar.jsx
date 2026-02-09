import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { 
  Plus, Search, BookOpen, LayoutGrid, ChevronDown, 
  MessageSquare, FolderOpen, MoreHorizontal, Settings, LogOut
} from "lucide-react";

export function Sidebar() {
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isKnowledgeBaseOpen, setIsKnowledgeBaseOpen] = useState(false);

  const historyItems = [
    "生成统计图,统计每个数据周...",
    "帮我生成折线图,两个纵坐标...",
    "生成饼图,展示各平台...",
    "近三天小红书的热搜词top5...",
    "请阅读上述会议录音文档...",
    "我想分析618的活动情况...",
    "对比2025年春节期间一线...",
    "请分析这份11月5日的各事业...",
  ];

  const knowledgeBaseItems = [
    "分析助手知识库",
    "Friday知识库",
    "酒旅知识库"
  ];

  return (
    <div className="w-64 h-screen bg-[#F7F8FA] flex flex-col border-r border-gray-100 flex-shrink-0 font-sans text-sm">
      {/* Header */}
      <div className="p-4 pb-2">
        <h1 className="text-lg font-bold text-gray-800mb-4px-2">商业分析助手</h1>
        <Button className="w-full justify-start bg-blue-50 text-blue-600 hover:bg-blue-100 border-none rounded-lg h-9 mb-3shadow-none">
          <Plus className="mr-2 h-4 w-4" />
          新建任务
        </Button>

        <div className="relative mb-2">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
          <Input 
            placeholder="搜索任务" 
            className="pl-9 h-9 bg-transparent border-none shadow-none focus-visible:ring-0 placeholder:text-gray-400 hover:bg-gray-100transition-colors rounded-lg" 
          />
        </div></div>

      <ScrollArea className="flex-1 px-3">
        <div className="space-y-1">
          <Button 
            variant="ghost" 
            className="w-full justify-start h-9 text-gray-600 font-normal hover:bg-gray-200/50"
            onClick={() => setIsKnowledgeBaseOpen(!isKnowledgeBaseOpen)}
          >
            <BookOpen className="mr-2 h-4 w-4" />
            知识库
            <span className="ml-auto text-gray-400">
              <ChevronDown className={`h-3 w-3 transition-transform duration-200 ${isKnowledgeBaseOpen ? '' : '-rotate-90'}`} />
            </span>
          </Button>
          
          {isKnowledgeBaseOpen && (
            <div className="space-y-0.5 animate-in slide-in-from-top-1 fade-in duration-200 mb-2 pl-4">
               {knowledgeBaseItems.map((item, index) => (
                  <Button 
                    key={index} 
                    variant="ghost" 
                    className="w-full justify-start h-8 text-gray-500 font-normal hover:bg-gray-200/50 text-xs truncate"
                  >
                    <span className="w-1 h-1 rounded-full bg-gray-300 mr-2 flex-shrink-0" />
                    <span className="truncate">{item}</span>
                  </Button>
               ))}
            </div>
          )}

          <Button variant="ghost" className="w-full justify-start h-9 text-gray-600 font-normal hover:bg-gray-200/50">
            <LayoutGrid className="mr-2 h-4 w-4" />
            工作流
          </Button>
        </div>

        <div className="mt-6 mb-2 px-2 flex items-center justify-between text-xs text-gray-500 font-medium">
          <span>我的项目</span>
          <ChevronDown className="h-3 w-3 cursor-pointer" />
        </div><Button variant="ghost" className="w-full justify-start h-9 text-gray-600 font-normal hover:bg-gray-200/50">
          <FolderOpen className="mr-2 h-4 w-4" />
          创建项目
        </Button>

        <div 
          className="mt-6 mb-2 px-2 flex items-center justify-between text-xs text-gray-500 font-medium cursor-pointer hover:text-gray-700 transition-colors select-none group"
          onClick={() => setIsHistoryOpen(!isHistoryOpen)}
        >
          <span>历史任务</span>
          <ChevronDown className={`h-3 w-3 transition-transform duration-200 text-gray-400 group-hover:text-gray-600 ${isHistoryOpen ? '' : '-rotate-90'}`} />
        </div>
        
        {isHistoryOpen && (
          <div className="space-y-0.5 animate-in slide-in-from-top-1 fade-in duration-200">
            {historyItems.map((item, index) => (
              <Button 
                key={index} 
                variant="ghost" 
                className="w-full justify-start h-8 text-gray-600 font-normal hover:bg-gray-200/50 text-xs truncate block text-left"
                title={item}
              >
                <span className="truncate w-full block">{item}</span>
              </Button>
            ))}
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
