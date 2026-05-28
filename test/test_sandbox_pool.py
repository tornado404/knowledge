"""测试 E2B 沙盒连接池"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from kgsrc.knowledge_vector.multi_agent.sandbox_pool import (
    SandboxPool, SandboxInstance, get_sandbox_pool
)


class TestSandboxInstance:
    """测试 SandboxInstance 数据类"""

    def test_creation(self):
        instance = SandboxInstance(
            id="test-id",
            sandbox=None,
            is_busy=False
        )
        assert instance.id == "test-id"
        assert instance.is_busy is False
        assert instance.sandbox is None


class TestSandboxPool:
    """测试 SandboxPool"""

    def test_creation(self):
        pool = SandboxPool(pool_size=3, timeout=60)
        assert pool.pool_size == 3
        assert pool.timeout == 60
        assert len(pool._sandboxes) == 0  # 延迟创建

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self):
        pool = SandboxPool(api_key="", pool_size=2)
        await pool.initialize()
        # 无 API key 时应该初始化成功但不使用沙盒
        assert pool._initialized is True

    @pytest.mark.asyncio
    async def test_acquire_release(self):
        pool = SandboxPool(pool_size=2)
        await pool.initialize()

        # 添加一个沙盒实例用于测试
        instance = SandboxInstance(id="sandbox-1", sandbox=None, is_busy=False)
        pool._sandboxes["sandbox-1"] = instance

        # 获取
        sandbox_id = await pool.acquire()
        assert sandbox_id == "sandbox-1"
        assert pool._sandboxes["sandbox-1"].is_busy is True

        # 释放
        await pool.release(sandbox_id)
        assert pool._sandboxes["sandbox-1"].is_busy is False

    @pytest.mark.asyncio
    async def test_acquire_no_available(self):
        pool = SandboxPool(pool_size=1)
        await pool.initialize()

        instance = SandboxInstance(id="sandbox-1", sandbox=None, is_busy=True)
        pool._sandboxes["sandbox-1"] = instance

        # 无可用沙盒
        sandbox_id = await pool.acquire()
        assert sandbox_id is None

    @pytest.mark.asyncio
    async def test_close(self):
        pool = SandboxPool(pool_size=2)
        await pool.initialize()

        # 添加沙盒实例
        mock_sandbox = MagicMock()
        instance = SandboxInstance(id="sandbox-1", sandbox=mock_sandbox, is_busy=False)
        pool._sandboxes["sandbox-1"] = instance

        await pool.close()
        assert len(pool._sandboxes) == 0
        assert pool._initialized is False


class TestGetSandboxPool:
    """测试全局沙盒池获取"""

    def test_get_sandbox_pool(self):
        pool = get_sandbox_pool()
        assert isinstance(pool, SandboxPool)

    def test_same_instance(self):
        pool1 = get_sandbox_pool()
        pool2 = get_sandbox_pool()
        assert pool1 is pool2
