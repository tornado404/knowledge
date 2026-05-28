"""Bash 命令执行工具"""
import asyncio
from typing import Optional, List

from .base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Bash 命令执行工具"""

    def __init__(
        self,
        timeout: int = 30,
        allowed_commands: Optional[List[str]] = None,
        blocked_commands: Optional[List[str]] = None,
    ):
        super().__init__(
            name="bash",
            description="Execute bash commands"
        )
        self.timeout = timeout
        # 默认允许的命令（安全列表）
        self.allowed_commands = allowed_commands or [
            "ls", "cat", "grep", "find", "echo", "pwd", "cd", "dir"
        ]
        # 默认阻止的危险命令
        self.blocked_commands = blocked_commands or [
            "rm -rf /", "dd", "mkfs", "fdisk", ">:", "curl", "wget",
            "ssh", "scp", "sftp", "ftp", "telnet",
        ]

    async def execute(self, command: str, **kwargs) -> ToolResult:
        """执行 Bash 命令"""
        # 安全检查
        if not self._is_command_safe(command):
            return ToolResult(
                success=False,
                error=f"Command not allowed: {command}"
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )

            if proc.returncode == 0:
                return ToolResult(
                    success=True,
                    output=stdout.decode() if stdout else ""
                )
            else:
                return ToolResult(
                    success=False,
                    output=stdout.decode() if stdout else "",
                    error=stderr.decode() if stderr else "Unknown error"
                )
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(
                success=False,
                error=f"Command timed out after {self.timeout}s"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )

    def _is_command_safe(self, command: str) -> bool:
        """检查命令是否安全"""
        cmd_lower = command.lower()

        # 检查是否在阻止列表中
        for blocked in self.blocked_commands:
            if blocked in cmd_lower:
                return False

        # 如果有允许列表，检查是否在列表中
        if self.allowed_commands:
            cmd_start = cmd_lower.split()[0] if cmd_lower.split() else ""
            if cmd_start not in self.allowed_commands:
                # 允许的命令后面可以跟路径参数
                for allowed in self.allowed_commands:
                    if cmd_lower.startswith(allowed):
                        return True
                return False

        return True
