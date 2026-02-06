
import { motion, AnimatePresence } from 'framer-motion';
import useEmblaCarousel from 'embla-carousel-react';
import { FileSpreadsheet, User, RefreshCw, Sparkles, Zap, FileText, Compass, ChevronRight, PieChart, X, ArrowUpRight, ChevronLeft, Flame } from 'lucide-react';
import { cn } from '@/lib/utils';
import React, { useCallback, useRef, useEffect, useState } from 'react';
const CaseCard = ({ item, isSelected, isActive, onClick, onHover }) => {
  return (
    <motion.div
      layoutId={`card-${item.id}`}
      className={cn(
        "flex-shrink-0 w-64 h-36 rounded-2xl border cursor-pointer relative overflow-hidden transition-all duration-500 mx-2 bg-white",
        isActive 
            ? "scale-105 border-gray-200 shadow-[0_8px_30px_rgb(0,0,0,0.06)] z-10" 
            : "scale-95 border-gray-100 opacity-80 hover:opacity-100 hover:scale-100 shadow-sm",
        isSelected && "opacity-0"
      )}
      onClick={() => onClick(item)}
      onMouseEnter={() => onHover(item)}
    >
        {/* 背景图层 - 模拟卡片风格的底图 */}
        <div className="absolute inset-0 z-0 bg-gradient-to-br from-gray-50 to-slate-50">
             <img 
                src={`https://nocode.meituan.com/photo/search?keyword=${item.imageKeyword},minimalist,white background,high quality&width=400&height=250`}
                alt=""
                className="w-full h-full object-cover opacity-90"
             />
             {/* 统一色调遮罩 */}
             <div className="absolute inset-0 bg-white/20 mix-blend-overlay" />
             {/* 渐变遮罩，确保下方文字清晰 */}
             <div className="absolute inset-0 bg-gradient-to-t from-white via-white/50 to-transparent" />
        </div>

        <div className="relative z-10 flex flex-col h-full p-4">
            <div className="flex items-start justify-between">
                {/* 左上角图标：小尺寸深色圆形，与其他组件风格统一 */}
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#4A4A4A] text-white shadow-sm backdrop-blur-sm border border-white/10">
                    <item.icon className="w-3.5 h-3.5" />
                </div>
            </div>
            
            <div className="mt-auto">
                {/* 修改了标题样式：移除了 font-bold 和 text-gray-900，改为更柔和的 font-medium 和 text-gray-800 */}
                <h4 className="font-medium text-sm text-gray-800 mb-1 leading-tight tracking-tight">
                    {item.title}
                </h4>
                <p className="text-[10px] text-gray-500 line-clamp-2 leading-relaxed font-medium">
                    {item.desc}
                </p>
            </div>
        </div>
    </motion.div>
  );
};

export const CaseDeck = ({ isOpen, onClose, onSelect, onCardHover, onActiveChange }) => {
  const deckRef = useRef(null);
  const [emblaRef, emblaApi] = useEmblaCarousel({ loop: true, align: 'center', skipSnaps: false });
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const resumeTimerRef = useRef(null);

  // 点击外部关闭逻辑
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (deckRef.current && deckRef.current.contains(event.target)) {
        return;
      }
      if (event.target.closest('#mystery-bulb-trigger')) {
        return;
      }
      onClose();
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // 图标定义：Flame(热门), User(历史推荐/人相关), Compass(新方向探索)
  const allCases = [
    {
      id: 1,
      category: "数据清洗",
      title: "Q1电商销售数据异常值处理",
      desc: "检测销售额列中的离群值,并使用线性插值法进行填补,输出清洗后的Excel。",
      prompt: "请帮我检测这份Q1销售数据Excel中的异常值,特别是销售额那一列。对于离群值,请使用线性插值法填补,并给我一个清洗后的版本。",
      icon: User, // 历史推荐：基于上传行为
      color: "bg-blue-500",
      imageKeyword: "excel data spreadsheet,chart"
    },
    {
      id: 2,
      category: "图表生成",
      title: "用户留存与获客成本双轴图",
      desc: "绘制双轴图表,左轴显示月度留存率,右轴显示CAC,分析两者相关性。",
      prompt: "根据提供的数据,帮我画一个双轴图。左轴是月度用户留存率(折线),右轴是获客成本CAC(柱状),我想看下这两者最近半年有没有相关性。",
      icon: Flame, // 热门 Showcase
      color: "bg-rose-500",
      imageKeyword: "growth chart,analytics graph"
    },
    {
      id: 3,
      category: "报告润色",
      title: "新产品上市复盘报告优化",
      desc: "精简这份复盘文档的语言,使其更具商务专业感,并生成执行摘要。",
      prompt: "阅读这份新产品上市复盘文档,帮我润色一下语言,使其听起来更专业、精简。另外,请在开头生成一段200字的执行摘要。",
      icon: Compass, // 新方向/Goodcase
      color: "bg-purple-500",
      imageKeyword: "business document,writing"
    },
    {
      id: 4,
      category: "竞品分析",
      title: "瑞幸vs星巴克价格带对比",
      desc: "抓取并分析两大品牌的SKU价格分布,生成箱线图对比。",
      prompt: "我想对比一下瑞幸和星巴克目前的主力产品价格带。请帮我分析他们的SKU价格分布,最好能生成一个箱线图来直观对比。",
      icon: Compass, // 新方向/Goodcase
      color: "bg-violet-500",
      imageKeyword: "coffee chart,comparison graph"
    },
     {
      id: 5,
      category: "库存管理",
      title: "预测下季度SKU库存周转",
      desc: "基于历史出库数据,预测下季度各SKU的周转天数,标记滞销风险。",
      prompt: "这是过去一年的出库记录,请基于此预测下个季度各SKU的库存周转天数,并把可能出现滞销风险的商品标记出来。",
      icon: User, // 历史推荐：基于已有数据延伸
      color: "bg-indigo-500",
      imageKeyword: "warehouse boxes,logistics chart"
    },
    {
      id: 6,
      category: "社媒分析",
      title: "小红书爆款笔记关键词",
      desc: "分析美妆类目Top100笔记，提取高频关键词和封面设计规律。",
      prompt: "帮我分析一下最近一周小红书美妆类目的Top100爆款笔记，提取出标题中的高频关键词，并总结一下封面图的视觉特点。",
      icon: Flame, // 热门 Showcase
      color: "bg-orange-500",
      imageKeyword: "social media mobile,likes"
    },
    {
      id: 7,
      category: "市场调研",
      title: "新能源车主画像调研",
      desc: "基于问卷数据，分析不同年龄段车主对续航里程的敏感度。",
      prompt: "这是我们收集的新能源车主问卷数据，请分析不同年龄段（20-30，30-40，40+）的车主对'续航里程'这一指标的关注度差异。",
      icon: Compass, // 新方向/Goodcase
      color: "bg-teal-500",
      imageKeyword: "electric car,survey chart"
    },
    {
      id: 8,
      category: "会议提效",
      title: "自动生成会议纪要",
      desc: "提取录音中的关键决策点和待办事项，生成结构化纪要。",
      prompt: "请根据这段会议录音转文字的内容，整理一份结构化的会议纪要，重点列出达成的决议和后续的To-do List。",
      icon: Flame, // 热门 Showcase
      color: "bg-yellow-500",
      imageKeyword: "meeting room,microphone"
    }
  ];

  const [displayCases, setDisplayCases] = useState(allCases.slice(0, 5));

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    // 模拟刷新延迟和随机排序
    setTimeout(() => {
        const shuffled = [...allCases].sort(() => 0.5 - Math.random());
        setDisplayCases(shuffled.slice(0, 5));
        setIsRefreshing(false);
        if (emblaApi) emblaApi.scrollTo(0);
    }, 500);
  }, [allCases, emblaApi]);

  // 监听 Embla 滚动事件，更新选中索引并通知父组件
  const onSelectEmbla = useCallback(() => {
    if (!emblaApi) return;
    const index = emblaApi.selectedScrollSnap();
    setSelectedIndex(index);
    // 注意：这里使用 displayCases 而不是 allCases
    if (onActiveChange && displayCases[index]) {
        onActiveChange(displayCases[index].prompt);
    }
  }, [emblaApi, onActiveChange, displayCases]);

  useEffect(() => {
    if (!emblaApi) return;
    onSelectEmbla();
    emblaApi.on('select', onSelectEmbla);
    return () => {
        emblaApi.off('select', onSelectEmbla);
    };
  }, [emblaApi, onSelectEmbla]);

  // 自动播放逻辑 - 5秒一次
  useEffect(() => {
    if (!isPlaying || !emblaApi) return;
    const interval = setInterval(() => {
        emblaApi.scrollNext();
    }, 5000); 
    return () => clearInterval(interval);
  }, [isPlaying, emblaApi]);

  // 暂停并延迟恢复播放
  const pauseAndResumeLater = useCallback(() => {
    setIsPlaying(false);
    if (resumeTimerRef.current) {
        clearTimeout(resumeTimerRef.current);
    }
    resumeTimerRef.current = setTimeout(() => {
        setIsPlaying(true);
    }, 10000); 
  }, []);
  
  // 清理定时器
  useEffect(() => {
      return () => {
          if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current);
      }
  }, []);

  const scrollPrev = useCallback(() => {
    if (emblaApi) emblaApi.scrollPrev();
    pauseAndResumeLater();
  }, [emblaApi, pauseAndResumeLater]);

  const scrollNext = useCallback(() => {
    if (emblaApi) emblaApi.scrollNext();
    pauseAndResumeLater();
  }, [emblaApi, pauseAndResumeLater]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: 'auto', marginTop: 16 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            className="w-full overflow-hidden"
        >
            <div ref={deckRef} className="relative group/deck">
                 <div className="flex items-center justify-between px-2 mb-1">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-gray-700">个性化灵感库推荐</span>
                        <button 
                            onClick={handleRefresh}
                            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-400 hover:text-blue-600 transition-all group/btn"
                            title="换一批"
                        >
                            <RefreshCw className={cn(
                                "w-3.5 h-3.5 transition-transform duration-500",
                                isRefreshing ? "animate-spin" : "group-hover/btn:rotate-180"
                            )} />
                        </button>
                    </div>

                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-full hover:bg-gray-100"
                    >
                        <X className="w-3 h-3" />
                    </button>
                 </div>
                
                {/* 左右导航按钮 */}
                <button
                    onClick={scrollPrev}
                    className="absolute left-0 top-[55%] -translate-y-1/2 z-20 w-8 h-8 flex items-center justify-center bg-white/90 backdrop-blur-sm rounded-full shadow-md border border-gray-100 text-gray-500 hover:text-gray-800 hover:bg-white transition-all opacity-0 group-hover/deck:opacity-100"
                >
                    <ChevronLeft className="w-4 h-4" />
                </button>

                {/* Embla Carousel - 减小了上下padding，拉近与标题的距离 */}
                <div 
                    className="overflow-hidden py-2 px-1" 
                    ref={emblaRef}
                    onClick={pauseAndResumeLater}
                >
                    <div className="flex -ml-4 items-center h-40">
                        {displayCases.map((item, index) => (
                            <div className="flex-[0_0_auto] pl-4" key={item.id}>
                                <CaseCard 
                                    item={item} 
                                    isActive={index === selectedIndex}
                                    onClick={onSelect}
                                    onHover={onCardHover}
                                />
                            </div>
                        ))}
                    </div>
                </div>

                <button
                    onClick={scrollNext}
                    className="absolute right-0 top-[55%] -translate-y-1/2 z-20 w-8 h-8 flex items-center justify-center bg-white/90 backdrop-blur-sm rounded-full shadow-md border border-gray-100 text-gray-500 hover:text-gray-800 hover:bg-white transition-all opacity-0 group-hover/deck:opacity-100"
                >
                    <ChevronRight className="w-4 h-4" />
                </button>
                
                {/* 渐变遮罩 */}
                <div className="absolute top-8 bottom-4 left-0 w-12 bg-gradient-to-r from-white via-white/80 to-transparent pointer-events-none z-10" />
                <div className="absolute top-8 bottom-4 right-0 w-12 bg-gradient-to-l from-white via-white/80 to-transparent pointer-events-none z-10" />
            </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CaseDeck;
