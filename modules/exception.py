# coding:utf-8
"""异常定义"""


class ResponseError(Exception):
    """Exception for abnormal response."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class IPBannedError(ResponseError):
    """Exception for IP banned in e-hentai."""

    def __init__(self, h, m, s):
        super().__init__('IP address has been temporarily banned.')
        self.h = h
        self.m = m
        self.s = s


class LimitationReachedError(ResponseError):
    """Exception for limitation has reached."""

    def __init__(self, page):
        super().__init__(page)


class WrongAddressError(ResponseError):
    """Exception for providing wrong address."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class ValidationError(Exception):
    """Exception for wrong user-id or password or other error about validation."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)
