# coding:utf-8
"""异常定义"""


class ResponseError(Exception):
    """非法响应异常"""

    def __init__(self, msg: any):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class ValidationError(Exception):
    """身份认证错误异常"""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


###############
# Ehentai异常 #
##############


class IPBannedError(ResponseError):
    """IP被封禁异常"""

    def __init__(self, h: int, m: int, s: int):
        """
        Args:
            h: 封禁时长（小时）
            m: 封禁时长（分钟）
            s: 封禁时长（秒）
        """
        super().__init__('IP address has been temporarily banned.')
        self.h = h
        self.m = m
        self.s = s


class LimitationReachedError(ResponseError):
    """达到下载限额异常"""

    def __init__(self, pn: int):
        """
        Args:
            pn: 达到下载限额时的页码
        """
        super().__init__('Download limitation reached.')
        self.pn = pn


###############
# 通用异常 #
##############


class WrongAddressError(ResponseError):
    """地址错误异常"""

    def __init__(self, addr: str):
        """
        Args:
            addr: 错误的地址
        """
        super().__init__('Unavailable address.')
        self.addr = addr
