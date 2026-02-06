
import CaseDeck from './CaseDeck';
import { motion, AnimatePresence } from 'framer-motion';
import MysteryCube from './MysteryCube';
import { HardDrive, FileSpreadsheet, Monitor, AtSign, Sparkles, Search, Cloud, Database, FolderUp, Plus, ArrowUp, ChevronRight } from 'lucide-react';
import { KnowledgeBaseDialog } from './KnowledgeBaseDialog';
import { DropdownMenuItem, DropdownMenuTrigger, DropdownMenuContent, DropdownMenu } from '@/components/ui/dropdown-menu';
import React, { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
export function ChatInputArea({ onSend }) {
  const [inputValue, setInputValue] = useState('');
  const [isDeckOpen, setIsDeckOpen] = useState(false);
  const [placeholder, setPlaceholder] = useState("尽管问,带图也行");
  const [phantomText, setPhantomText] = useState('');
  const [suggestionData, setSuggestionData] = useState(null); // 存储完整的建议对象
  
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  
  const hasContent = inputValue.trim().length > 0;

  // 数据分析师常用案例数据
  const suggestions = [
    { 
      text: "接着做：昨日未完成的漏斗图绘制", 
      emoji: "⏳"
    },
    { 
      text: "瑞幸本周华南区门店销量分析", 
      emoji: "☕" 
    },
    { 
      text: "来做一个新的工作流", 
      emoji: "✨" 
    }
  ];

  // 模拟 L1, L2, L3 补全逻辑
  useEffect(() => {
    if (!inputValue || inputValue.length < 1) {
      setPhantomText('');
      setSuggestionData(null);
      return;
    }

    const lowerInput = inputValue.toLowerCase();
    let bestMatch = null;

    // 1. 尝试 L1/L2/L3 匹配逻辑
    // 为了 Phantom Text 效果，优先匹配那些 "inputValue 是其前缀" 的项

    const possibleMatches = [];

    // L2: 分析模态预测 (意图层) - 必须严格前缀匹配才能做 Phantom Text
    if ('为什么'.startsWith(inputValue) && inputValue.length >= 1) {
       // 特殊情况：如果用户还没打完 "为什么"，不展示补全，或者是展示完整建议？
       // 这里为了演示 Phantom Text，我们假设用户输入 "为什么" 后才补全后面长句
    }
    
    if (inputValue.startsWith('为什么') || inputValue.startsWith('why')) {
      possibleMatches.push({
        type: 'L2',
        content: `为什么五月销量下滑？执行多维归因分析`,
      });
    }

    if (inputValue.startsWith('预测') || inputValue.startsWith('fore')) {
      possibleMatches.push({
        type: 'L2',
        content: `预测下季度SKU库存周转，使用Prophet模型`,
      });
    }

    // L3: 文档识别
    if ((inputValue.includes('归因') || inputValue.includes('attribution')) && !inputValue.includes(']')) {
         // 这种非前缀匹配的，通常不适合做 Phantom Text（除非做复杂的后缀拼接），
         // 这里简单处理：如果用户正好输入到 "归因"，我们补全整句，但用户体验可能突兀。
         // 我们改为：如果用户输入 "针对"，补全 L3
         if (inputValue.startsWith('针对')) {
            possibleMatches.push({
                type: 'L3',
                content: '针对“Q1_华南销售明细”，基于 [毛利率] 字段进行异动归因分析',
            });
         }
    }
    
    // L1: 基础词补全 (如果用户输入了完整的前缀)
    // 比如输入 "xiao"，因为是拼音，无法直接做 Phantom Text (xiao -> 销售额，无法拼接)。
    // 只有当用户输入中文 "销" 时，补全 "售额"
    if ('销售额'.startsWith(inputValue)) {
        possibleMatches.push({ content: '销售额' });
    }
    if ('本周'.startsWith(inputValue)) {
        possibleMatches.push({ content: '本周华南区门店销量分析' });
    }

    // 查找第一个符合 "Strict Prefix" 的匹配项
    bestMatch = possibleMatches.find(item => item.content.toLowerCase().startsWith(lowerInput));

    if (bestMatch) {
      // 计算剩余部分
      // 注意：这里使用 slice 切割，确保大小写匹配正确（虽然 content 通常是标准格式）
      const remainder = bestMatch.content.slice(inputValue.length);
      setPhantomText(remainder);
      setSuggestionData(bestMatch);
    } else {
      setPhantomText('');
      setSuggestionData(null);
    }

  }, [inputValue]);

  const handleCardSelect = (item) => {
    if (onSend) {
      onSend(item.prompt);
    } else {
      setIsDeckOpen(false);
      setInputValue(item.prompt);
      setPlaceholder("尽管问,带图也行");
    }
  };

  const handleCardHover = (item) => {
    setPlaceholder(item.prompt);
  };
  
  const handleActiveChange = (prompt) => {
    if (isDeckOpen) {
        setInputValue(prompt);
    }
  };

  const toggleDeck = () => {
    if (isDeckOpen) {
        setPlaceholder("尽管问,带图也行");
        setInputValue('');
    }
    setIsDeckOpen(!isDeckOpen);
  };

  const handleManualSend = (overrideValue) => {
    const finalValue = overrideValue || inputValue;
    if (finalValue.trim().length > 0 && onSend) {
        onSend(finalValue);
        setInputValue('');
        setPhantomText('');
    }
  };

  const handleKeyDown = (e) => {
    // 处理 Phantom Text 补全
    if (phantomText && e.key === 'ArrowRight') {
        e.preventDefault();
        setInputValue(inputValue + phantomText);
        setPhantomText('');
        return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleManualSend();
    }
  };

  const triggerFileUpload = () => {
      fileInputRef.current?.click();
  };

  return (
    <div className="flex flex-col items-center justify-center w-full max-w-3xl mx-auto px-4 relative">
      {/* Brand Title */}
      <div className="mb-20 text-center">
         <h1 className="text-5xl font-bold tracking-tight text-gray-900 mb-2">BA Agent</h1>
      </div>

      {/* Input Container Wrapper */}
      <div className="w-full relative z-10">
        
        <div id="mystery-bulb-trigger" className="absolute -top-12 left-0 z-20">
           <MysteryCube onClick={toggleDeck} disableTooltip={isDeckOpen} />
        </div>

        {/* Main Input Box */}
        <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-gray-200 to-gray-100 rounded-[2rem] opacity-50 blur group-hover:opacity-75 transition duration-500"></div>
            <div className="relative bg-white rounded-[1.8rem] shadow-lg border border-gray-100 p-4 transition-all duration-300">
                
                {/* 
                   Phantom Text Overlay Layer 
                   它必须与下面的 textarea 拥有完全相同的字体、padding、line-height 等属性，才能完美重叠。
                */}
                <div className="absolute inset-0 p-4 pointer-events-none overflow-hidden" aria-hidden="true">
                    {/* 这里的样式必须复刻 textarea 的样式 */}
                    <div className="w-full text-base font-medium pl-2 whitespace-pre-wrap break-words font-sans leading-normal">
                        <span className="opacity-0">{inputValue}</span>
                        <span className="text-gray-300">{phantomText}</span>
                    </div>
                </div>

                {/* Actual Input Textarea */}
                <motion.textarea 
                    layout
                    ref={inputRef}
                    className="w-full resize-none border-none outline-none text-base text-gray-800 placeholder:text-gray-400 min-h-[60px] max-h-[200px] bg-transparent font-medium pl-2 relative z-10 font-sans leading-normal"
                    placeholder={placeholder}
                    rows={1}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    spellCheck={false}
                />
                
                {/* Bottom Toolbar */}
                <div className="flex items-center justify-between mt-2 px-1">
                    <div className="flex items-center gap-2">
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button size="icon" variant="ghost" className="h-9 w-9 rounded-full hover:bg-gray-100 text-gray-500 data-[state=open]:bg-gray-100 data-[state=open]:text-gray-900 transition-all focus-visible:ring-0 focus-visible:ring-offset-0">
                                    <Plus className="h-5 w-5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="start" sideOffset={8} className="w-48 p-1 bg-white/95 backdrop-blur-sm rounded-xl shadow-[0_10px_38px_-10px_rgba(22,23,24,0.35),0_10px_20px_-15px_rgba(22,23,24,0.2)] border-gray-100">
                                {/* Local Upload Group */}
                                <div className="px-2 py-1.5 text-[10px] font-bold text-gray-400 uppercase tracking-wider">上传数据</div>
                                
                                <DropdownMenuItem onClick={triggerFileUpload} className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-700 focus:bg-blue-50 focus:text-blue-700 cursor-pointer outline-none transition-colors">
                                    <div className="flex items-center justify-center w-6 h-6 rounded-md bg-blue-100 text-blue-600">
                                        <Monitor className="h-3.5 w-3.5" />
                                    </div>
                                    <span>桌面文件</span>
                                    {/* Hidden File Input */}
                                    <input 
                                        type="file" 
                                        ref={fileInputRef} 
                                        className="hidden" 
                                        onChange={(e) => console.log('File selected:', e.target.files[0])}
                                    />
                                </DropdownMenuItem>
                                
                                <DropdownMenuItem className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-orange-50 hover:text-orange-700 focus:bg-orange-50 focus:text-orange-700 cursor-pointer outline-none transition-colors">
                                    <div className="flex items-center justify-center w-6 h-6 rounded-md bg-orange-100 text-orange-600">
                                        <FolderUp className="h-3.5 w-3.5" />
                                    </div>
                                    <span>选择文件夹</span>
                                </DropdownMenuItem>

                                {/* Cloud Data Group */}
                                <div className="h-px bg-gray-100 my-1 mx-2" />
                                <div className="px-2 py-1.5 text-[10px] font-bold text-gray-400 uppercase tracking-wider">导入数据源</div>

                                <DropdownMenuItem className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-purple-50 hover:text-purple-700 focus:bg-purple-50 focus:text-purple-700 cursor-pointer outline-none transition-colors">
                                    <div className="flex items-center justify-center w-6 h-6 rounded-md bg-purple-100 text-purple-600">
                                        <Database className="h-3.5 w-3.5" />
                                    </div>
                                    <span>沧澜数据集</span>
                                </DropdownMenuItem>
                                
                                <DropdownMenuItem className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-green-50 hover:text-green-700 focus:bg-green-50 focus:text-green-700 cursor-pointer outline-none transition-colors">
                                    <div className="flex items-center justify-center w-6 h-6 rounded-md bg-green-100 text-green-600">
                                        <Cloud className="h-3.5 w-3.5" />
                                    </div>
                                    <span>个人空间</span>
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                        
                        {/* Modified Knowledge Base Trigger Button */}
                        <KnowledgeBaseDialog>
                            <Button variant="ghost" className="h-8 rounded-full bg-transparent text-gray-400 text-xs hover:bg-gray-100 hover:text-gray-700 border border-transparent px-3 min-w-[40px] justify-center transition-all duration-200">
                                <AtSign className="h-4 w-4" />
                            </Button>
                        </KnowledgeBaseDialog>

                        {/* Phantom Text Hint (Optional) */}
                        {phantomText && (
                            <span className="text-[10px] text-gray-400 bg-gray-50 px-2 py-1 rounded border border-gray-100 animate-in fade-in slide-in-from-left-2">
                                按 <span className="font-bold font-mono">→</span> 补全
                            </span>
                        )}
                    </div>

                    <div className="flex items-center gap-3">
                         <div className="flex items-center text-xs text-gray-500 font-medium cursor-pointer hover:text-gray-800 transition-colors">
                            longcat <span className="ml-1">▼</span>
                         </div>
                         <Button 
                            size="icon" 
                            disabled={!hasContent}
                            onClick={() => handleManualSend()}
                            className={`h-9 w-9 rounded-full transition-all duration-200 ${
                              hasContent 
                                ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md' 
                                : 'bg-gray-200 text-white cursor-not-allowed'
                            }`}
                         >
                            <ArrowUp className="h-5 w-5" />
                         </Button>
                    </div>
                </div>
            </div>
        </div>
      </div>

      <div className="w-full">
         <CaseDeck 
            isOpen={isDeckOpen} 
            onClose={() => { 
                setIsDeckOpen(false); 
                setPlaceholder("尽管问,带图也行"); 
                setInputValue('');
            }}
            onSelect={handleCardSelect}
            onCardHover={handleCardHover}
            onActiveChange={handleActiveChange}
         />
      </div>

      {/* 悬浮气泡区域 */}
      <AnimatePresence>
        {!isDeckOpen && (
            <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="flex flex-col items-start gap-2 mt-4 w-full px-2"
            >
                {suggestions.map((item, index) => (
                <div
                    key={index}
                    onClick={() => onSend ? onSend(item.text) : setInputValue(item.text)}
                    className="group/bubble flex items-center gap-2 relative w-auto max-w-full bg-white border border-gray-200/60 rounded-2xl py-2 px-3 text-left shadow-sm hover:shadow-md hover:-translate-y-0.5 hover:border-gray-300 transition-all duration-300 cursor-pointer"
                >
                    <span className="text-base leading-none">{item.emoji}</span>
                    <span className="text-gray-600 text-xs sm:text-sm font-medium group-hover/bubble:text-gray-900 transition-colors">
                    {item.text}
                    </span>
                </div>
                ))}
            </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
