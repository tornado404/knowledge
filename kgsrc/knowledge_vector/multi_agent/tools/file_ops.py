"""文件操作工具集"""
import asyncio
from pathlib import Path
from typing import List, Optional

from .base import BaseTool, ToolResult


class LsTool(BaseTool):
    """列出目录内容"""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="ls",
            description="List directory contents"
        )
        self.base_path = Path(base_path)

    async def execute(self, path: str = ".", **kwargs) -> ToolResult:
        """列出目录内容"""
        try:
            target = self.base_path / path
            if not target.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            items = []
            for item in target.iterdir():
                items.append(f"{'d' if item.is_dir() else 'f'} {item.name}")

            return ToolResult(
                success=True,
                output="\n".join(items)
            )
        except PermissionError:
            return ToolResult(success=False, error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CatTool(BaseTool):
    """读取文件内容"""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="cat",
            description="Read file contents"
        )
        self.base_path = Path(base_path)

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        """读取文件内容"""
        try:
            target = self.base_path / file_path
            if not target.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")

            if target.is_dir():
                return ToolResult(success=False, error=f"Is a directory: {file_path}")

            content = target.read_text(encoding="utf-8")
            return ToolResult(success=True, output=content)
        except PermissionError:
            return ToolResult(success=False, error="Permission denied")
        except UnicodeDecodeError:
            return ToolResult(success=False, error="File is not text-encoded")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GrepTool(BaseTool):
    """文本搜索工具"""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="grep",
            description="Search for pattern in files"
        )
        self.base_path = Path(base_path)

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        recursive: bool = True,
        file_pattern: str = "*",
        **kwargs
    ) -> ToolResult:
        """在文件中搜索模式"""
        try:
            import fnmatch

            target = self.base_path / path
            if not target.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            matches = []
            if recursive and target.is_dir():
                for file_path in target.rglob(file_pattern):
                    if file_path.is_file():
                        try:
                            for line_num, line in enumerate(
                                file_path.read_text(encoding="utf-8").splitlines(),
                                1
                            ):
                                if pattern.lower() in line.lower():
                                    matches.append(
                                        f"{file_path}:{line_num}:{line.strip()}"
                                    )
                        except (PermissionError, UnicodeDecodeError):
                            continue
            else:
                if target.is_file():
                    for line_num, line in enumerate(
                        target.read_text(encoding="utf-8").splitlines(), 1
                    ):
                        if pattern.lower() in line.lower():
                            matches.append(f"{target}:{line_num}:{line.strip()}")

            return ToolResult(
                success=True,
                output="\n".join(matches) if matches else "No matches found",
                metadata={"match_count": len(matches)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FindTool(BaseTool):
    """文件查找工具"""

    def __init__(self, base_path: str = "."):
        super().__init__(
            name="find",
            description="Find files by name"
        )
        self.base_path = Path(base_path)

    async def execute(
        self,
        name_pattern: str,
        path: str = ".",
        file_type: Optional[str] = None,  # "f" or "d"
        **kwargs
    ) -> ToolResult:
        """查找文件"""
        try:
            target = self.base_path / path
            if not target.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            matches = []
            for file_path in target.rglob(name_pattern):
                if file_type == "f" and file_path.is_file():
                    matches.append(str(file_path.relative_to(self.base_path)))
                elif file_type == "d" and file_path.is_dir():
                    matches.append(str(file_path.relative_to(self.base_path)))
                elif file_type is None:
                    matches.append(str(file_path.relative_to(self.base_path)))

            return ToolResult(
                success=True,
                output="\n".join(matches) if matches else "No matches found",
                metadata={"found_count": len(matches)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
