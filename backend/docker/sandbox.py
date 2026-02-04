"""
Docker Python 沙盒执行器

提供安全的 Python 代码执行环境，使用 Docker 容器隔离
"""

import os
import json
import tempfile
from typing import Any, Dict, Optional, List
from pathlib import Path
import docker

from config import get_config


class DockerSandbox:
    """
    Docker Python 沙盒

    在隔离的 Docker 容器中执行 Python 代码
    """

    def __init__(self):
        """初始化 Docker 客户端"""
        self.client = docker.from_env()
        self.config = get_config()

    def execute_python(
        self,
        code: str,
        timeout: int = 30,
        memory_limit: str = "128m",
        cpu_limit: str = "0.5",
        network_disabled: bool = True,
    ) -> Dict[str, Any]:
        """
        在 Docker 容器中执行 Python 代码

        Args:
            code: 要执行的 Python 代码
            timeout: 执行超时时间（秒）
            memory_limit: 内存限制 (如 "128m")
            cpu_limit: CPU 限制 (如 "0.5")
            network_disabled: 是否禁用网络

        Returns:
            执行结果字典
        """
        # 准备临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False
        ) as f:
            f.write(code)
            code_file = f.name

        try:
            # 容器配置
            container_config = {
                'image': self.config.docker.image,
                'command': f'python {code_file}',
                'volumes': {
                    os.path.dirname(code_file): {'bind': '/workspace', 'mode': 'ro'}
                },
                'mem_limit': memory_limit,
                'cpu_quota': int(float(cpu_limit) * 100000),
                'cpu_period': 100000,
                'network_disabled': network_disabled,
                'detach': True,
                'remove': True,
            }

            # 创建并启动容器
            container = self.client.containers.run(**container_config)

            # 等待容器完成
            result = container.wait(timeout=timeout)

            # 获取日志
            logs = container.logs().decode('utf-8')

            return {
                'success': result['StatusCode'] == 0,
                'stdout': logs,
                'stderr': '',
                'exit_code': result['StatusCode'],
            }

        except docker.errors.ContainerError as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': e.exit_status,
            }
        except docker.errors.APIError as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Docker API error: {str(e)}",
                'exit_code': -1,
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Unexpected error: {str(e)}",
                'exit_code': -1,
            }
        finally:
            # 清理临时文件
            if os.path.exists(code_file):
                os.remove(code_file)

    def execute_command(
        self,
        command: str,
        timeout: int = 30,
        memory_limit: str = "128m",
        cpu_limit: str = "0.5",
        network_disabled: bool = True,
    ) -> Dict[str, Any]:
        """
        在 Docker 容器中执行命令

        Args:
            command: 要执行的命令
            timeout: 执行超时时间（秒）
            memory_limit: 内存限制
            cpu_limit: CPU 限制
            network_disabled: 是否禁用网络

        Returns:
            执行结果字典
        """
        try:
            # 使用同步执行来正确捕获输出
            output = self.client.containers.run(
                image=self.config.docker.image,
                command=command,
                mem_limit=memory_limit,
                cpu_quota=int(float(cpu_limit) * 100000),
                cpu_period=100000,
                network_disabled=network_disabled,
                remove=True,
                # 不使用 detach，这样可以直接获取输出
            )

            # output 是字节串
            stdout = output.decode('utf-8').strip()

            return {
                'success': True,
                'stdout': stdout,
                'stderr': '',
                'exit_code': 0,
            }

        except docker.errors.ContainerError as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': e.exit_status,
            }
        except docker.errors.APIError as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Docker API error: {str(e)}",
                'exit_code': -1,
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Unexpected error: {str(e)}",
                'exit_code': -1,
            }

    def test_container(self) -> bool:
        """
        测试 Docker 容器是否可用

        Returns:
            Docker 是否可用
        """
        try:
            # 尝试运行一个简单的容器
            result = self.client.containers.run(
                image="python:3.12-slim",
                command="python --version",
                remove=True,
            )
            version = result.decode('utf-8').strip()
            return "Python 3.12" in version
        except Exception as e:
            print(f"Docker test failed: {e}")
            return False

    def close(self):
        """关闭 Docker 客户端"""
        self.client.close()


# 全局沙盒实例
_sandbox: Optional[DockerSandbox] = None


def get_sandbox() -> DockerSandbox:
    """
    获取全局 Docker 沙盒实例

    Returns:
        DockerSandbox 实例
    """
    global _sandbox

    if _sandbox is None:
        _sandbox = DockerSandbox()

    return _sandbox


def execute_python_safely(
    code: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    安全执行 Python 代码的便捷函数

    Args:
        code: 要执行的 Python 代码
        timeout: 执行超时时间（秒）

    Returns:
        执行结果字典
    """
    sandbox = get_sandbox()

    # 从配置获取限制
    config = get_config()

    return sandbox.execute_python(
        code=code,
        timeout=timeout or config.docker.timeout,
        memory_limit=config.docker.memory_limit,
        cpu_limit=config.docker.cpu_limit,
        network_disabled=config.docker.network_disabled,
    )


# 导出
__all__ = [
    "DockerSandbox",
    "get_sandbox",
    "execute_python_safely",
]
