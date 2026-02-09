import React, { createContext, useContext, useEffect, useState } from 'react';

const NoCodeSDKContext = createContext();

const useNoCodeSDKAvailability = () => {
  const [isAvailable, setIsAvailable] = useState(() => typeof window.NoCode !== 'undefined');

  useEffect(() => {
    if (isAvailable) return;

    const checkAvailability = () => {
      if (typeof window.NoCode !== 'undefined') {
        setIsAvailable(true);
        return true;
      }
      return false;
    };
    if (checkAvailability()) return;

    const interval = setInterval(() => {
      if (checkAvailability()) {
        clearInterval(interval);
      }
    }, 100);

    const timeout = setTimeout(() => {
      clearInterval(interval);
    }, 10000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [isAvailable]);

  return isAvailable;
};

export const useNoCodeSDK = () => {
  const context = useContext(NoCodeSDKContext);
  if (!context) {
    throw new Error('useNoCodeSDK must be used within a NoCodeProvider');
  }
  return context;
};

export const NoCodeProvider = ({ children }) => {
  const isAvailable = useNoCodeSDKAvailability();
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [initError, setInitError] = useState(null);

  useEffect(() => {
    if (!isAvailable || isReady || isLoading || initError) return;

    const initSDK = async () => {
      setIsLoading(true);
      setInitError(null);

      try {
        const modules = import.meta.glob('@/integrations/supabase/client.js');
        let supabaseConfig = Object.values(modules).length ? await Object.values(modules)[0]() : null;
        const result = await window.NoCode.init({
          env: import.meta.env.MODE,
          chatId: import.meta.env.VITE_CHAT_ID,
          chatEnv: import.meta.env.VITE_CHAT_ENV,
          disableSSO: import.meta.env.VITE_SSO_DISABLED === 'true',
          supabase: supabaseConfig?.supabase,
        });

        if (result.success) {
          setIsReady(true);
        } else {
          setInitError(new Error(result.error || 'NoCode SDK 初始化失败'));
        }
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : '未知错误';
        setInitError(new Error(errorMsg));
      } finally {
        setIsLoading(false);
      }
    };

    initSDK();
  }, [isAvailable, isReady, isLoading, initError]);

  // 仅当 SDK 已加载且正在初始化时显示加载态；其余情况（SDK 不可用、初始化失败、初始化成功）都渲染页面，避免白屏
  const showApp = !isAvailable || isReady || initError != null || !isLoading;

  const value = {
    isReady: isReady || !isAvailable,
  };

  return (
    <NoCodeSDKContext.Provider value={value}>
      {showApp ? children : (
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          <p className="text-gray-500">加载中...</p>
        </div>
      )}
    </NoCodeSDKContext.Provider>
  );
};


