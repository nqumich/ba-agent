import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Upload, FileText, Image as ImageIcon, X, CloudUpload, Loader2 } from "lucide-react";
import { toast } from "sonner";

export function UploadCaseDialog({ children }) {
  const [open, setOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // 表单状态
  const [formData, setFormData] = useState({
    title: '',
    category: '',
    tags: '',
    desc: ''
  });

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      // 模拟添加文件
      const newFiles = Array.from(e.dataTransfer.files).map(file => ({
          name: file.name,
          size: (file.size / 1024 / 1024).toFixed(2) + ' MB',
          type: file.type
      }));
      setFiles([...files, ...newFiles]);
    }
  };

  const removeFile = (index) => {
      const newFiles = [...files];
      newFiles.splice(index, 1);
      setFiles(newFiles);
  };

  const handleInputChange = (key, value) => {
    setFormData(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
      // 表单验证
      if (!formData.title.trim()) {
          toast.error("请输入案例标题");
          return;
      }
      if (!formData.category) {
          toast.error("请选择所属分类");
          return;
      }
      
      setIsSubmitting(true);

      // 模拟网络请求延迟
      try {
          await new Promise(resolve => setTimeout(resolve, 1500));
          
          toast.success("案例发布成功", {
              description: "您的案例已提交审核，审核通过后将展示在案例广场。",
          });

          // 关闭弹窗并重置表单
          setOpen(false);
          setFormData({
            title: '',
            category: '',
            tags: '',
            desc: ''
          });
          setFiles([]);

      } catch (error) {
          toast.error("发布失败，请稍后重试");
      } finally {
          setIsSubmitting(false);
      }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] bg-white gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-6 py-4 border-b border-gray-100 bg-white">
          <DialogTitle className="text-lg font-semibold text-gray-900">上传新案例</DialogTitle>
          <p className="text-sm text-gray-500 mt-1">分享您的数据分析案例，让更多人受益。</p>
        </DialogHeader>
        
        <div className="p-6 space-y-5">
           {/* Title */}
           <div className="space-y-2">
             <Label htmlFor="title" className="text-sm font-medium text-gray-700">案例标题 <span className="text-red-500">*</span></Label>
             <Input 
                id="title" 
                placeholder="给您的案例起个响亮的名字，例如：瑞幸Q3销售分析" 
                className="bg-gray-50 border-gray-200 focus:bg-white transition-colors" 
                value={formData.title}
                onChange={(e) => handleInputChange('title', e.target.value)}
             />
           </div>

           <div className="grid grid-cols-2 gap-4">
                {/* Category */}
                <div className="space-y-2">
                    <Label htmlFor="category" className="text-sm font-medium text-gray-700">所属分类 <span className="text-red-500">*</span></Label>
                    <Select 
                        value={formData.category} 
                        onValueChange={(val) => handleInputChange('category', val)}
                    >
                        <SelectTrigger className="bg-gray-50 border-gray-200 focus:bg-white">
                            <SelectValue placeholder="选择分类" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="excel">Excel分析</SelectItem>
                            <SelectItem value="chart">生成图表</SelectItem>
                            <SelectItem value="report">报告润色</SelectItem>
                            <SelectItem value="workflow">执行工作流</SelectItem>
                            <SelectItem value="other">其他</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                
                 {/* Tags */}
                 <div className="space-y-2">
                    <Label htmlFor="tags" className="text-sm font-medium text-gray-700">标签 (可选)</Label>
                    <Input 
                        id="tags" 
                        placeholder="输入标签，用逗号分隔" 
                        className="bg-gray-50 border-gray-200 focus:bg-white" 
                        value={formData.tags}
                        onChange={(e) => handleInputChange('tags', e.target.value)}
                    />
                 </div>
           </div>


           {/* Description */}
           <div className="space-y-2">
             <Label htmlFor="desc" className="text-sm font-medium text-gray-700">案例描述</Label>
             <Textarea 
                id="desc" 
                placeholder="简要描述这个案例的功能亮点、使用场景以及解决的问题..." 
                className="min-h-[100px] bg-gray-50 border-gray-200 focus:bg-white resize-none" 
                value={formData.desc}
                onChange={(e) => handleInputChange('desc', e.target.value)}
             />
           </div>

           {/* File Upload Simulation */}
           <div className="space-y-2">
             <Label className="text-sm font-medium text-gray-700">上传附件/封面</Label>
             <div 
                className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50 hover:border-gray-300'}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
             >
                <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mb-3">
                    <CloudUpload className="h-6 w-6" />
                </div>
                <p className="text-sm font-medium text-gray-900">点击或拖拽文件到此处</p>
                <p className="text-xs text-gray-500 mt-1">支持 .xlsx, .pdf, .png, .jpg (最大 50MB)</p>
             </div>

             {/* File List */}
             {files.length > 0 && (
                 <div className="mt-3 space-y-2">
                     {files.map((file, index) => (
                         <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-100">
                             <div className="flex items-center gap-3 overflow-hidden">
                                 <div className="w-8 h-8 rounded bg-white flex items-center justify-center border border-gray-100 text-gray-500">
                                     <FileText className="h-4 w-4" />
                                 </div>
                                 <div className="flex flex-col min-w-0">
                                     <span className="text-xs font-medium text-gray-700 truncate">{file.name}</span>
                                     <span className="text-[10px] text-gray-400">{file.size}</span>
                                 </div>
                             </div>
                             <button onClick={() => removeFile(index)} className="text-gray-400 hover:text-red-500 p-1">
                                 <X className="h-4 w-4" />
                             </button>
                         </div>
                     ))}
                 </div>
             )}
           </div>
        </div>
        
        <DialogFooter className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center gap-2">
           <Button variant="outline" onClick={() => setOpen(false)} disabled={isSubmitting} className="bg-white border-gray-200 text-gray-700 hover:bg-gray-50">
                取消
           </Button>
           <Button onClick={handleSubmit} disabled={isSubmitting} className="bg-blue-600 hover:bg-blue-700 text-white shadow-sm min-w-[100px]">
                {isSubmitting ? (
                    <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        发布中
                    </>
                ) : (
                    "确认发布"
                )}
           </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
