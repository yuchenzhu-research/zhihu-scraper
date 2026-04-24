"""
CLI 模块 - 知乎爬虫命令行接口
"""

__all__ = ["app", "main"]


def __getattr__(name: str):
    if name in __all__:
        from .app import app, main

        return {"app": app, "main": main}[name]
    raise AttributeError(name)
