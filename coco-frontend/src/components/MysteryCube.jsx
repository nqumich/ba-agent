import { motion, AnimatePresence } from 'framer-motion';
import { TooltipContent, TooltipTrigger, Tooltip } from '@/components/ui/tooltip';
import { Sparkles, Lightbulb } from 'lucide-react';
import React, { useState, useEffect, useRef } from 'react';

const MysteryCube = ({ onClick, disableTooltip }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [autoOpen, setAutoOpen] = useState(false);
  const timerRef = useRef(null);

  // 处理点击：触发父组件逻辑 + 关闭自动提示
  const handleClick = (e) => {
    setAutoOpen(false);
    if (onClick) onClick(e);
  };

  // 监听禁用状态变化
  useEffect(() => {
    if (disableTooltip) {
      setAutoOpen(false);
    }
  }, [disableTooltip]);

  // 空闲检测逻辑：5秒无操作自动显示提示
  useEffect(() => {
    // 如果气泡已经自动显示，或被禁用，则不再进行空闲检测
    if (autoOpen || disableTooltip) return;

    const resetTimer = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        if (!disableTooltip) {
          setAutoOpen(true);
        }
      }, 5000);
    };

    // 初始启动计时
    resetTimer();

    // 任何交互都重置计时
    const handleActivity = () => resetTimer();
    
    // 监听全局事件来判断用户是否活跃
    const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
    events.forEach(event => window.addEventListener(event, handleActivity));

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      events.forEach(event => window.removeEventListener(event, handleActivity));
    };
  }, [autoOpen, disableTooltip]);

  // 如果被禁用，则不显示 Tooltip
  const showTooltip = !disableTooltip && (autoOpen || isHovered);

  return (
    <div className="relative">
        <Tooltip open={showTooltip} delayDuration={300}>
            <TooltipTrigger asChild>
                <motion.div
                    className="relative cursor-pointer group"
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                    onClick={handleClick}
                    initial={{ y: 0 }}
                    animate={{ 
                        y: isHovered ? -4 : 0,
                        rotate: isHovered ? [0, -10, 10, 0] : 0,
                    }}
                    transition={{
                        y: {
                            duration: 0.4,
                            ease: "easeOut",
                        },
                        rotate: {
                            duration: 0.5,
                            ease: "easeInOut",
                            loop: Infinity,
                            repeatDelay: 1
                        }
                    }}
                >
                    {/* Glow Effect */}
                    <motion.div
                        className="absolute inset-0 bg-yellow-400/40 blur-xl rounded-full"
                        animate={{
                            opacity: isHovered ? 1 : 0,
                            scale: isHovered ? 1.4 : 0.8,
                        }}
                        transition={{ duration: 0.3 }}
                    />

                    {/* Bulb Container */}
                    <div className={`
                        relative w-9 h-9 flex items-center justify-center
                        bg-white/80 backdrop-blur-md border border-yellow-100/50 
                        rounded-full shadow-sm transition-all duration-300
                        ${isHovered ? 'bg-yellow-50 border-yellow-400 text-yellow-600 shadow-yellow-200' : 'text-gray-500 hover:text-yellow-500'}
                    `}>
                        <Lightbulb 
                            className={`w-5 h-5 transition-all duration-300 ${isHovered ? 'fill-yellow-400 text-yellow-600' : 'fill-transparent'}`} 
                            strokeWidth={2}
                        />
                        
                        {/* Sparkles decoration */}
                        <AnimatePresence>
                            {isHovered && (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0, x: -5, y: 5 }}
                                    animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
                                    exit={{ opacity: 0, scale: 0 }}
                                    className="absolute -top-1 -right-1"
                                >
                                    <Sparkles className="w-3 h-3 text-yellow-500 fill-yellow-500" />
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </motion.div>
            </TooltipTrigger>
            <TooltipContent 
                side="top" 
                className="bg-white/95 backdrop-blur-sm text-slate-600 border-none shadow-[0_8px_30px_rgb(0,0,0,0.08)] text-xs font-medium px-4 py-2 mb-3 rounded-full flex items-center justify-center"
            >
                <p>还没思路？点亮灵感</p>
            </TooltipContent>
        </Tooltip>
    </div>
  );
};

export default MysteryCube;
