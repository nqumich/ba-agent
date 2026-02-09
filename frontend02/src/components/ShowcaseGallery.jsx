
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { UploadCaseDialog } from './UploadCaseDialog';
import { AvatarFallback, AvatarImage, Avatar } from '@/components/ui/avatar';
import { FileSpreadsheet, Sparkles, Upload, Clock, FilePenLine, Eye, PieChart, Search, ChevronUp, LayoutGrid, Share2, ArrowUpDown, Layers, Flame } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
// 模拟数据生成器
const generateItems = (category, count = 8) => {
  return Array.from({ length: count }).map((_, i) => ({
    id: `${category}-${i}`,
    title: `${category} - 示例项目 ${i + 1}`,
    author: "AI助手",
    views: Math.floor(Math.random() * 50000) + 1000,
    // 模拟最近30天内的随机日期
    date: new Date(Date.now() - Math.floor(Math.random() * 30 * 24 * 60 * 60 * 1000)).toISOString(),
    tag: category === 'Excel分析' ? 'Data' : 
         category === '生成图表' ? 'Viz' : 
         category === '报告润色' ? 'Doc' : 
         category === '执行工作流' ? 'Flow' : 'Case',
    imageKeyword: category === 'Excel分析' ? 'excel,data,spreadsheet,minimalist' : 
                  category === '生成图表' ? 'chart,graph,analytics,clean' : 
                  category === '报告润色' ? 'document,writing,paper,workspace' : 
                  category === '执行工作流' ? 'workflow,process,connection' :
                  'technology,abstract,minimalist',
    icon: category === 'Excel分析' ? <FileSpreadsheet className="h-3.5 w-3.5" /> :
          category === '生成图表' ? <PieChart className="h-3.5 w-3.5" /> :
          category === '报告润色' ? <FilePenLine className="h-3.5 w-3.5" /> :
          category === '执行工作流' ? <Share2 className="h-3.5 w-3.5" /> :
          <Sparkles className="h-3.5 w-3.5" />
  }));
};

const categories = [
  { id: 'recommend', label: '推荐', icon: Sparkles },
  { id: 'square', label: '案例广场', icon: LayoutGrid },
  { id: 'excel', label: 'Excel分析', icon: FileSpreadsheet },
  { id: 'chart', label: '生成图表', icon: PieChart },
  { id: 'report', label: '报告润色', icon: FilePenLine },
  { id: 'workflow', label: '执行工作流', icon: Share2 },
];

const mockData = {
  recommend: [
    { id: 1, title: "西高地小狗公益站", author: "Kimi", views: 16283, date: "2023-10-15", tag: "Web", imageKeyword: "white terrier,dog,cute", icon: <Share2 className="w-3.5 h-3.5" /> },
    { id: 2, title: "《口技》国画风互动网页", author: "User123", views: 21847, date: "2023-10-12", tag: "H5", imageKeyword: "chinese painting,traditional art", icon: <Share2 className="w-3.5 h-3.5" /> },
    { id: 3, title: "教父电影回顾网页", author: "MovieBuff", views: 26310, date: "2023-10-10", tag: "Web", imageKeyword: "godfather,movie,dark", icon: <FilePenLine className="w-3.5 h-3.5" /> },
    { id: 4, title: "股票组合回测分析", author: "TraderPro", views: 33297, date: "2023-10-08", tag: "Fin", imageKeyword: "stock market,finance chart", icon: <PieChart className="w-3.5 h-3.5" /> },
    { id: 5, title: "羊毛运动鞋电商平台", author: "ShopMaster", views: 25264, date: "2023-10-05", tag: "Shop", imageKeyword: "wool shoes,running,product", icon: <FileSpreadsheet className="w-3.5 h-3.5" /> },
    { id: 6, title: "英伟达股价财报分析", author: "Analyst", views: 30877, date: "2023-10-01", tag: "Data", imageKeyword: "nvidia,chip,technology", icon: <FileSpreadsheet className="w-3.5 h-3.5" /> },
    { id: 7, title: "科隆教堂英文图解", author: "Traveler", views: 10295, date: "2023-09-28", tag: "Art", imageKeyword: "cologne cathedral,architecture", icon: <FilePenLine className="w-3.5 h-3.5" /> },
    { id: 8, title: "极简阅读器", author: "Reader", views: 21317, date: "2023-09-25", tag: "App", imageKeyword: "minimalist reader,app interface", icon: <Share2 className="w-3.5 h-3.5" /> },
  ],
  square: [
    { id: 'sq1', title: "Q3销售数据复盘", author: "叶子钰", views: 0, date: new Date().toISOString(), tag: "Report", imageKeyword: "sales report,chart,meeting", icon: <FilePenLine className="w-3.5 h-3.5" /> },
    { id: 'sq2', title: "奶茶店选址分析模型", author: "叶子钰", views: 12, date: new Date(Date.now() - 86400000).toISOString(), tag: "Model", imageKeyword: "map,location,store", icon: <FileSpreadsheet className="w-3.5 h-3.5" /> },
    ...generateItems('社区精选', 6)
  ],
  excel: generateItems('Excel分析'),
  chart: generateItems('生成图表'),
  report: generateItems('报告润色'),
  workflow: generateItems('执行工作流'),
};

const GalleryCard = ({ item }) => (
  <div className="group cursor-pointer flex flex-col gap-2">
    <div className="relative aspect-[16/10] overflow-hidden rounded-xl bg-gray-100 border border-gray-100">
       <img 
         src={`https://nocode.meituan.com/photo/search?keyword=${item.imageKeyword}&width=600&height=375`}
         alt={item.title}
         className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
       />
       
       {/* 左上角图标：圆形深色背景 */}
       <div className="absolute top-2.5 left-2.5 flex items-center justify-center w-7 h-7 rounded-full bg-[#4A4A4A] text-white shadow-sm backdrop-blur-sm z-10 border border-white/10">
         {item.icon}
       </div>

       {/* 悬停遮罩 */}
       <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors duration-300 pointer-events-none" />
    </div>
    
    <div>
      <h3 className="text-sm font-semibold text-gray-900 leading-tight mb-1.5 line-clamp-1 group-hover:text-blue-600 transition-colors">
        {item.title}
      </h3>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-1.5 hover:text-gray-700 transition-colors">
          <Avatar className="h-4 w-4">
              <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${item.author}`} />
              <AvatarFallback>{item.author[0]}</AvatarFallback>
          </Avatar>
          <span className="truncate max-w-[80px]">{item.author}</span>
        </div>
        <div className="flex items-center gap-1">
          <Eye className="h-3 w-3" />
          <span>{item.views.toLocaleString()}</span>
        </div>
      </div>
    </div>
  </div>
);

export function ShowcaseGallery({ onClose }) {
  const [activeTab, setActiveTab] = useState('recommend');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOrder, setSortOrder] = useState('latest'); // 'latest' | 'popular'

  // 过滤与排序逻辑
  const items = useMemo(() => {
    let currentItems = mockData[activeTab] || [];
    
    // 1. 过滤
    if (searchQuery) {
        const query = searchQuery.toLowerCase();
        currentItems = currentItems.filter(item => 
            item.title.toLowerCase().includes(query) ||
            item.author.toLowerCase().includes(query) ||
            item.tag.toLowerCase().includes(query)
        );
    }

    // 2. 排序 (仅在有数据时)
    if (currentItems.length > 0) {
        // 创建副本以避免修改原数组
        currentItems = [...currentItems]; 
        
        if (sortOrder === 'popular') {
            currentItems.sort((a, b) => b.views - a.views);
        } else if (sortOrder === 'latest') {
            // 假设 item 有 date 字段，如果没有则保持原序或随机
            currentItems.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
        }
    }

    return currentItems;
  }, [activeTab, searchQuery, sortOrder]);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Sticky Header */}
      <div className="flex-none px-6 pt-6 pb-2 border-b border-gray-100 bg-white/80 backdrop-blur-xl z-30 sticky top-0">
        <div className="flex items-center justify-between max-w-7xl mx-auto w-full">
            <Tabs 
                value={activeTab} 
                onValueChange={(val) => { 
                    setActiveTab(val); 
                    setSearchQuery(''); // 切换 Tab 时重置搜索
                    setSortOrder('latest'); // 切换 Tab 时重置排序
                }} 
                className="w-full"
            >
              <div className="flex items-center justify-between w-full">
                  <TabsList className="bg-transparent h-auto p-0 gap-8 justify-start">
                    {categories.map((cat) => (
                      <TabsTrigger 
                        key={cat.id} 
                        value={cat.id}
                        className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-gray-900 text-gray-500 text-base font-medium px-0 pb-3 rounded-none border-b-2 border-transparent data-[state=active]:border-gray-900 transition-all hover:text-gray-700"
                      >
                        {cat.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  <Button 
                    variant="ghost" 
                    className="gap-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-full px-4" 
                    onClick={onClose}
                  >
                    回到首页
                    <ChevronUp className="h-4 w-4" />
                  </Button>
              </div>
            </Tabs>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto bg-white scrollbar-hide">
        <div className="max-w-7xl mx-auto p-6 min-h-full">
             
             {/* 顶部搜索框与功能区 */}
             <div className="flex flex-col gap-4 mb-8">
                <div className="flex items-center justify-between gap-4">
                    <div className="relative w-full max-w-xs group">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 group-focus-within:text-gray-600 transition-colors" />
                        <Input 
                            placeholder="搜索案例、作者或关键词..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10 h-11 rounded-full bg-gray-50 border-gray-200 hover:bg-gray-100 focus:bg-white focus:ring-2 focus:ring-gray-100 transition-all text-sm shadow-sm justify-start"
                        />
                    </div>

                    {/* 仅在案例广场显示上传按钮 */}
                    {activeTab === 'square' && (
                        <UploadCaseDialog>
                            <Button className="bg-blue-600 hover:bg-blue-700 text-white shadow-sm gap-2 rounded-full px-5 h-11">
                                <Upload className="h-4 w-4" />
                                上传案例
                            </Button>
                        </UploadCaseDialog>
                    )}
                </div>
                
                {/* 排序过滤器 - 仅在案例广场显示 */}
                {activeTab === 'square' && (
                     <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-400 text-xs mr-2">排序方式</span>
                        <div className="flex items-center gap-3">
                            <button 
                                onClick={() => setSortOrder('latest')}
                                className={`flex items-center gap-1.5 text-xs transition-all ${sortOrder === 'latest' ? 'text-gray-900 font-bold' : 'text-gray-400 hover:text-gray-600 font-medium'}`}
                            >
                                <Clock className="h-3 w-3" />
                                最新发布
                            </button>
                            
                            <span className="text-gray-300 text-xs">|</span>

                            <button 
                                onClick={() => setSortOrder('popular')}
                                className={`flex items-center gap-1.5 text-xs transition-all ${sortOrder === 'popular' ? 'text-gray-900 font-bold' : 'text-gray-400 hover:text-gray-600 font-medium'}`}
                            >
                                <Flame className="h-3 w-3" />
                                热门推荐
                            </button>
                        </div>
                     </div>
                )}
             </div>

             <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-10 pb-20 animate-in fade-in slide-in-from-bottom-4 duration-500">
                {items.length > 0 ? (
                    items.map((item) => (
                      <GalleryCard key={item.id} item={item} />
                    ))
                ) : (
                    <div className="col-span-full py-16 flex flex-col items-center justify-center text-gray-400">
                        <Search className="h-10 w-10 mb-3 opacity-20" />
                        <p className="text-sm">没有找到相关案例</p>
                    </div>
                )}
             </div>
        </div>
      </div>
    </div>
  );
}
