"""E2B 沙盒连接池管理"""
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
import uuid

from .tools.base import ToolResult
from knowledge_vector.config import config


@dataclass
class SandboxInstance:
    """沙盒实例"""
    id: str
    sandbox: Any  # e2b.Sandbox
    is_busy: bool = False
    created_at: float = 0


class SandboxPool:
    """E2B 沙盒连接池"""

    def __init__(
        self,
        pool_size: int = 5,
        timeout: int = 300,
        api_key: Optional[str] = None,
    ):
        self.pool_size = pool_size
        self.timeout = timeout
        self.api_key = api_key or config.e2b_api_key
        self._sandboxes: Dict[str, SandboxInstance] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self):
        """初始化沙盒连接池"""
        if self._initialized:
            return

        if not self.api_key:
            print("Warning: E2B_API_KEY not configured, sandbox will use fallback mode")
            self._initialized = True
            return

        try:
            # 预创建沙盒实例
            for i in range(self.pool_size):
                sandbox_id = str(uuid.uuid4())
                instance = SandboxInstance(
                    id=sandbox_id,
                    sandbox=None,  # 延迟创建
                    is_busy=False,
                )
                self._sandboxes[sandbox_id] = instance

            self._initialized = True
        except Exception as e:
            print(f"Error initializing sandbox pool: {e}")
            self._initialized = True  # 允许 fallback 模式

    async def acquire(self) -> Optional[str]:
        """获取一个可用的沙盒实例 ID"""
        async with self._lock:
            for sandbox_id, instance in self._sandboxes.items():
                if not instance.is_busy:
                    instance.is_busy = True
                    return sandbox_id
        return None

    async def release(self, sandbox_id: str):
        """释放沙盒实例回池中"""
        async with self._lock:
            if sandbox_id in self._sandboxes:
                self._sandboxes[sandbox_id].is_busy = False

    async def get_sandbox(self, sandbox_id: str) -> Optional[Any]:
        """获取沙盒实例"""
        if sandbox_id not in self._sandboxes:
            return None

        instance = self._sandboxes[sandbox_id]
        if instance.sandbox is None and self.api_key:
            try:
                from e2b import Sandbox
                instance.sandbox = await Sandbox.create(
                    api_key=self.api_key,
                    timeout=self.timeout
                )
            except Exception as e:
                print(f"Error creating sandbox: {e}")
                return None

        return instance.sandbox

    async def execute_in_sandbox(
        self,
        sandbox_id: str,
        command: str
    ) -> ToolResult:
        """在指定沙盒中执行命令"""
        sandbox = await self.get_sandbox(sandbox_id)
        if not sandbox:
            return ToolResult(
                success=False,
                error="Sandbox not available"
            )

        try:
            result = await asyncio.wait_for(
                sandbox.run_command(command),
                timeout=self.timeout
            )
            return ToolResult(
                success=result.exit_code == 0,
                output=result.stdout,
                error=result.stderr if result.exit_code != 0 else None
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command timed out after {self.timeout}s"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )

    async def write_file(
        self,
        sandbox_id: str,
        path: str,
        content: str
    ) -> ToolResult:
        """在沙盒中写文件"""
        sandbox = await self.get_sandbox(sandbox_id)
        if not sandbox:
            return ToolResult(
                success=False,
                error="Sandbox not available"
            )

        try:
            await asyncio.wait_for(
                sandbox.write_file(path, content),
                timeout=30
            )
            return ToolResult(success=True, output=f"Written to {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def read_file(
        self,
        sandbox_id: str,
        path: str
    ) -> ToolResult:
        """在沙盒中读文件"""
        sandbox = await self.get_sandbox(sandbox_id)
        if not sandbox:
            return ToolResult(
                success=False,
                error="Sandbox not available"
            )

        try:
            content = await asyncio.wait_for(
                sandbox.read_file(path),
                timeout=30
            )
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def close(self):
        """关闭所有沙盒实例"""
        async with self._lock:
            for instance in self._sandboxes.values():
                if instance.sandbox:
                    try:
                        await instance.sandbox.close()
                    except Exception:
                        pass
            self._sandboxes.clear()
            self._initialized = False


# 全局沙盒池实例
_sandbox_pool: Optional[SandboxPool] = None


def get_sandbox_pool() -> SandboxPool:
    """获取全局沙盒池实例"""
    global _sandbox_pool
    if _sandbox_pool is None:
        _sandbox_pool = SandboxPool(
            pool_size=config.sandbox_pool_size,
            timeout=config.sandbox_timeout,
            api_key=config.e2b_api_key,
        )
    return _sandbox_pool
