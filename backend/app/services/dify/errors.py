"""Dify 网关内部错误；对外响应不得透传上游详情。"""


class DifyError(RuntimeError):
    """Dify 网关错误基类。"""


class DifyConfigurationError(DifyError):
    """缺少或错误的本地 Dify 配置。"""


class DifyConnectionError(DifyError):
    """无法连接 Dify 或连接中断。"""


class DifyHTTPError(DifyError):
    """Dify 在流建立前返回非成功 HTTP 状态。"""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"Dify HTTP status {status_code}")
        self.status_code = status_code


class DifyProtocolError(DifyError):
    """SSE 或 Chatflow outputs 不符合约定。"""
