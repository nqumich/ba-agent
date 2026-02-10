import CaseDeck from './CaseDeck';
import { motion, AnimatePresence } from 'framer-motion';
import { FileSpreadsheet, AtSign, Sparkles, ChevronDown, Check, FolderUp, FileText, ChevronRight, HardDrive, Monitor, Search, Cloud, Database, X, Plus, ArrowUp } from 'lucide-react';
import { KnowledgeBaseDialog } from './KnowledgeBaseDialog';
import { DropdownMenuItem, DropdownMenuTrigger, DropdownMenuContent, DropdownMenu } from '@/components/ui/dropdown-menu';
import React, { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
export function ChatInputArea({ onSend }) {
  const [inputValue, setInputValue] = useState('');
  // 灵感库模式状态：'default' (个性化) | 'hot' (今日热点)
  const [deckMode, setDeckMode] = useState('default'); 
  
  const [placeholder, setPlaceholder] = useState("尽管问,带图也行");
  const [phantomText, setPhantomText] = useState('');
  const [suggestionData, setSuggestionData] = useState(null); // 存储完整的建议对象
  const [uploadedFiles, setUploadedFiles] = useState([]); // 存储已上传的文件
  const [currentModel, setCurrentModel] = useState("LongCat"); // 当前选择的模型

  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  
  const hasContent = inputValue.trim().length > 0 || uploadedFiles.length > 0;

  // 当有文件上传时，增加输入框的最小高度，确保至少能显示两行文字
  // 调整高度策略：基础高度设为 52px，确保无论是否有文件，默认都展示两行
  const inputMinHeight = "min-h-[52px]";

  // 可用的模型列表
  const models = [
    { id: "LongCat", name: "LongCat" },
    { id: "DeepSeek-V3", name: "DeepSeek-V3" },
    { id: "GPT-4o", name: "GPT-4o" },
    { id: "Claude-3.5", name: "Claude-3.5" }
  ];

  // 数据分析师常用案例数据
  const suggestions = [
    { 
      text: "今日热点", 
      emoji: "🔥" 
    },
    { 
      text: "接着做：昨日未完成的漏斗图绘制", 
      emoji: "⏳"
    }
  ];

  // 处理快捷指令点击
  const handleSuggestionClick = (item) => {
    if (item.text === "今日热点") {
        // Toggle 模式：如果是热点模式则切回默认，否则切到热点
        setDeckMode(prev => prev === 'hot' ? 'default' : 'hot');
    } else {
        // 原有逻辑
        if (onSend) {
            onSend(item.text);
        } else {
            setInputValue(item.text);
        }
    }
  };

  // 模拟 L1, L2, L3 补全逻辑
  useEffect(() => {
    if (!inputValue || inputValue.length < 1) {
      setPhantomText('');
      setSuggestionData(null);
      return;
    }

    const lowerInput = inputValue.toLowerCase();
    let bestMatch = null;

    const possibleMatches = [];
    
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
         if (inputValue.startsWith('针对')) {
            possibleMatches.push({
                type: 'L3',
                content: '针对“Q1_华南销售明细”，基于 [毛利率] 字段进行异动归因分析',
            });
         }
    }
    
    if ('销售额'.startsWith(inputValue)) {
        possibleMatches.push({ content: '销售额' });
    }
    if ('本周'.startsWith(inputValue)) {
        possibleMatches.push({ content: '本周华南区门店销量分析' });
    }

    // 查找第一个符合 "Strict Prefix" 的匹配项
    bestMatch = possibleMatches.find(item => item.content.toLowerCase().startsWith(lowerInput));

    if (bestMatch) {
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
      // 灵感库常驻，不需要关闭
      setInputValue(item.prompt);
      setPlaceholder("尽管问,带图也行");
    }
  };

  const handleCardHover = (item) => {
    setPlaceholder(item.prompt);
  };
  
  const handleActiveChange = (prompt) => {
    // 灵感库常驻，直接更新输入框
    setInputValue(prompt);
  };

  const handleManualSend = (overrideValue) => {
    const finalValue = overrideValue || inputValue;
    if ((finalValue.trim().length > 0 || uploadedFiles.length > 0) && onSend) {
        // 如果有文件，这里可以构建更复杂的消息对象，为了演示简单传递文本
        let messageText = finalValue;
        if (uploadedFiles.length > 0) {
            const filesDesc = uploadedFiles.map(f => `[文件: ${f.name}]`).join(' ');
            messageText = `${filesDesc} ${finalValue}`;
        }
        
        onSend(messageText);
        setInputValue('');
        setPhantomText('');
        setUploadedFiles([]); // 发送后清空文件
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
      // 这里的 click 会打开文件选择器
      fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    console.log("File changed", e.target.files);
    if (e.target.files && e.target.files.length > 0) {
        const newFiles = Array.from(e.target.files).map(file => ({
            name: file.name,
            size: formatFileSize(file.size),
            type: file.type,
            rawFile: file
        }));
        setUploadedFiles(prev => [...prev, ...newFiles]);
        // 清空 input value，允许重复上传同名文件
        e.target.value = ''; 
        // 聚焦回输入框
        setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleRemoveFile = (index) => {
      setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="flex flex-col items-center justify-center w-full max-w-3xl mx-auto px-4 relative">
      {/* Brand Title */}
      <div className="mb-10 text-center">
         <h1 className="text-5xl font-bold tracking-tight text-gray-900 mb-2">BA Agent</h1>
      </div>

      {/* Input Container Wrapper */}
      <div className="w-full relative z-10">
        
        {/* Main Input Box */}
        <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-gray-200 to-gray-100 rounded-[1.8rem] opacity-50 blur group-hover:opacity-75 transition duration-500"></div>
            
            {/* 核心输入区域容器：使用 flex-col 布局来容纳文件列表和输入框 */}
            <div className="relative bg-white rounded-[1.8rem] shadow-lg border border-gray-100 p-4 transition-all duration-300 flex flex-col gap-0">
                
                {/* File Preview List */}
                {uploadedFiles.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2 animate-in fade-in slide-in-from-top-2 duration-200 max-h-[120px] overflow-y-auto scrollbar-hide">
                        {uploadedFiles.map((file, index) => (
                            <div key={index} className="group relative flex items-center gap-2 bg-gray-50 border border-gray-100 rounded-lg p-1.5 pr-6 max-w-[180px] transition-all hover:bg-gray-100 hover:border-gray-200 hover:shadow-sm">
                                <div className="w-8 h-8 rounded-md bg-white border border-gray-100 flex items-center justify-center shrink-0 shadow-sm text-green-600">
                                    <FileSpreadsheet className="w-4 h-4" />
                                </div>
                                <div className="flex flex-col min-w-0">
                                    <span className="text-xs font-medium text-gray-900 truncate" title={file.name}>{file.name}</span>
                                    <span className="text-[10px] text-gray-400 font-medium leading-tight">{file.size}</span>
                                </div>
                                <button 
                                    onClick={() => handleRemoveFile(index)}
                                    className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center text-gray-500 hover:text-gray-800 transition-all opacity-0 group-hover:opacity-100 shadow-sm z-10"
                                >
                                    <X className="w-2.5 h-2.5" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* 
                   Input Wrapper: 
                   为了确保 Phantom Text 能够完美对齐 Textarea，我们需要一个相对定位的容器包裹它们俩。
                   这个容器在 flex-col 中，位于文件列表下方。
                */}
                <div className={`relative w-full transition-all duration-200 ${inputMinHeight}`}> 
                    {/* Phantom Text Overlay */}
                    <div className="absolute inset-0 pointer-events-none overflow-hidden py-2" aria-hidden="true">
                        <div className="w-full text-base font-normal pl-2 whitespace-pre-wrap break-words font-sans leading-relaxed">
                            <span className="opacity-0">{inputValue}</span>
                            <span className="text-gray-300">{phantomText}</span>
                        </div>
                    </div>

                    {/* Actual Input Textarea */}
                    <motion.textarea 
                        layout
                        ref={inputRef}
                        className={`w-full resize-none border-none outline-none text-base text-gray-600 placeholder:text-gray-400 ${inputMinHeight} max-h-[200px] bg-transparent font-normal pl-2 relative z-10 font-sans leading-relaxed py-2 transition-all duration-200`}
                        placeholder={placeholder}
                        rows={2}
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        spellCheck={false}
                    />
                </div>
                
                {/* Bottom Toolbar */}
                <div className="flex items-center justify-between mt-0 px-1">
                    <div className="flex items-center gap-2">
                        {/* Hidden File Input: 移到了 DropdownMenu 之外，确保 DOM 不会被卸载 */}
                        <input 
                            type="file" 
                            ref={fileInputRef} 
                            className="hidden" 
                            onChange={handleFileChange}
                            multiple
                            accept=".xlsx,.xls,.pdf,.doc,.docx,.ppt,.pptx,.txt,.csv,.jpg,.jpeg,.png"
                        />
                        
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
                         {/* Model Switcher */}
                         <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <div className="flex items-center text-xs text-gray-500 font-medium cursor-pointer hover:text-gray-800 transition-colors select-none gap-0.5">
                                    {currentModel} 
                                    <ChevronDown className="h-3 w-3" />
                                </div>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-36 bg-white/95 backdrop-blur-sm rounded-xl border-gray-100 shadow-[0_10px_38px_-10px_rgba(22,23,24,0.35),0_10px_20px_-15px_rgba(22,23,24,0.2)] p-1">
                                {models.map((model) => (
                                    <DropdownMenuItem 
                                        key={model.id} 
                                        onClick={() => setCurrentModel(model.name)}
                                        className={`text-xs cursor-pointer py-2 px-2 rounded-lg ${currentModel === model.name ? 'bg-gray-50 font-medium text-gray-900' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}
                                    >
                                        <div className="flex items-center justify-between w-full">
                                            {model.name}
                                            {currentModel === model.name && <Check className="h-3 w-3 text-blue-600" />}
                                        </div>
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                         </DropdownMenu>

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
        
         {/* 悬浮气泡区域 - 改为圆角胶囊风格 */}
        <AnimatePresence>
            <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-row flex-wrap items-center justify-center gap-3 mt-4 w-full px-2"
            >
                {suggestions.map((item, index) => (
                <div
                    key={index}
                    onClick={() => handleSuggestionClick(item)} // 使用新的点击处理函数
                    className={`group/bubble flex items-center gap-2 relative border rounded-full py-1.5 px-4 text-left transition-all duration-200 cursor-pointer ${
                         // 如果是今日热点且当前就是热点模式，给一个激活样式
                         item.text === "今日热点" && deckMode === 'hot'
                            ? 'bg-blue-50 border-blue-200'
                            : 'bg-white border-gray-200 hover:bg-gray-50 hover:border-gray-300'
                    }`}
                >
                    <span className="text-sm leading-none opacity-80">{item.emoji}</span>
                    <span className={`text-sm font-medium transition-colors ${
                        item.text === "今日热点" && deckMode === 'hot'
                        ? 'text-blue-700'
                        : 'text-gray-600 group-hover/bubble:text-gray-900'
                    }`}>
                    {item.text}
                    </span>
                </div>
                ))}
            </motion.div>
        </AnimatePresence>
      </div>

      <div className="w-full mt-8">
         <CaseDeck 
            isOpen={true} 
            onClose={() => {}} // 空函数，实际上现在是常驻的
            onSelect={handleCardSelect}
            onCardHover={handleCardHover}
            onActiveChange={handleActiveChange}
            mode={deckMode} // 传递模式 prop
         />
      </div>

    </div>
  );
}
