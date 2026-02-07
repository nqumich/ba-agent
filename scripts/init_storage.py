#!/usr/bin/env python3
"""
BA-Agent 存储初始化脚本

首次运行时配置存储目录
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.storage.config import init_storage


def main():
    """主函数"""
    # 检查是否已有配置
    storage_dir = os.getenv("BA_STORAGE_DIR")
    if storage_dir:
        print(f"✓ 使用环境变量 BA_STORAGE_DIR: {storage_dir}")
        print("\n存储配置已通过环境变量设置，无需初始化。")
        return

    # 运行初始化
    try:
        selected_dir = init_storage(interactive=True)
        print(f"\n✓ 存储目录: {selected_dir}")
        print(f"\n后续可以通过环境变量更改:")
        print(f"  export BA_STORAGE_DIR=/path/to/storage")

        # 写入 .env 文件提示
        env_file = project_root / ".env"
        if not env_file.exists():
            env_content = f"""# BA-Agent 环境变量配置
# 存储目录（可选，不设置则使用默认用户目录）
# BA_STORAGE_DIR=/custom/storage/path

# API 密钥（建议通过系统环境变量设置）
# ANTHROPIC_API_KEY=your_key_here
"""
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)
            print(f"\n✓ 已创建 .env 文件模板: {env_file}")

    except KeyboardInterrupt:
        print("\n\n初始化已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
