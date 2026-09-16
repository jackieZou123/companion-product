"""主动消息错误。独立模块，避免 pages 经包初始化去拉 store。"""


class NudgeNotFoundError(KeyError):
    pass
