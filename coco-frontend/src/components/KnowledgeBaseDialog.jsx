import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Search, Trash2, Plus, Inbox } from "lucide-react";

export function KnowledgeBaseDialog({ children }) {
  const [selectedCount, setSelectedCount] = useState(0);

  return (
    <Dialog>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[800px] p-0 gap-0 overflow-hidden bg-[#FAFAFA]">
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b border-gray-100 bg-white">
          <DialogTitle className="text-base font-medium text-gray-900">
            知识库 <span className="text-gray-400 font-normal text-sm ml-1">(最多选择9个)</span>
          </DialogTitle>
        </DialogHeader>

        {/* Content */}
        <div className="flex flex-col h-[520px]">
          {/* Search Bar */}
          <div className="px-6 py-3 bg-white">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input 
                placeholder="请输入知识库名称搜索" 
                className="pl-9 bg-white border-gray-200 focus-visible:ring-1 focus-visible:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex flex-1 overflow-hidden border-t border-gray-100">
            {/* Left Side: Library Selection */}
            <div className="w-1/2 border-r border-gray-100 bg-white flex flex-col">
              <Tabs defaultValue="assistant" className="w-full flex-1 flex flex-col">
                <div className="px-2 pt-2">
                   <TabsList className="w-full justify-start h-auto p-0 bg-transparent gap-2">
                      {["分析助手知识库", "Friday知识库", "酒旅知识库"].map(tab => (
                        <TabsTrigger 
                          key={tab} 
                          value={tab === "分析助手知识库" ? "assistant" : tab}
                          className="data-[state=active]:bg-gray-100 data-[state=active]:text-gray-900 text-gray-500 rounded-md px-3 py-1.5 text-xs transition-all"
                        >
                          {tab}
                        </TabsTrigger>
                      ))}
                   </TabsList>
                </div>
                
                <TabsContent value="assistant" className="flex-1 flex flex-col items-center justify-center p-6 m-0">
                    <div className="flex flex-col items-center text-center gap-3">
                        <div className="w-20 h-20 bg-gray-50 rounded-full flex items-center justify-center mb-2">
                             <Inbox className="h-10 w-10 text-gray-300" />
                        </div>
                        <p className="text-sm text-gray-500 font-medium">暂无内容，请创建知识库</p>
                        <Button className="bg-blue-600 hover:bg-blue-700 text-white h-8 px-6 rounded-md text-xs mt-2">
                            去创建
                        </Button>
                    </div>
                </TabsContent>
              </Tabs>
            </div>

            {/* Right Side: Selected Items */}
            <div className="w-1/2 bg-[#FAFAFA] flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100/50">
                    <span className="text-xs text-gray-500 font-medium">已选知识库 ({selectedCount}/9)</span>
                    <button className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 transition-colors">
                        <Trash2 className="h-3 w-3" />
                        清空已选
                    </button>
                </div>
                <div className="flex-1 p-4 relative overflow-hidden">
                     {/* 装饰性水印，模拟截图中的效果 */}
                     <div className="absolute inset-0 flex items-center justify-center opacity-[0.03] pointer-events-none select-none rotate-[-15deg] overflow-hidden">
                        <div className="grid grid-cols-2 gap-20 text-sm">
                             {Array.from({length: 12}).map((_, i) => (
                                 <span key={i}>NOCODE AGENT</span>
                             ))}
                        </div>
                     </div>
                </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-white border-t border-gray-100 flex justify-end gap-3">
            <DialogClose asChild>
                <Button variant="outline" className="h-9 px-6 rounded-md border-gray-200 text-gray-700 hover:bg-gray-50 hover:text-gray-900">
                    取消
                </Button>
            </DialogClose>
            <Button className="h-9 px-6 rounded-md bg-blue-600 hover:bg-blue-700 text-white shadow-sm">
                确认
            </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default KnowledgeBaseDialog;
