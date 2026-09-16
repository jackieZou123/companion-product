"""记忆错误。独立模块，避免 pages 经包初始化去拉 store。"""


class MemoryEventNotFoundError(KeyError):
    pass


class InvalidMemoryProfileError(ValueError):
    """槽位或取值不在允许集合里。"""
