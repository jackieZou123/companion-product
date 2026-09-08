"""对话错误。独立模块，避免 pages 经 dialogue 包初始化去拉 service。"""


class ConversationNotFoundError(KeyError):
    pass


class AdultNotConfirmedError(PermissionError):
    """创建会话必须显式确认成年。不能靠模型自觉。"""


class GenderRequiredError(ValueError):
    """创建会话必须选择性别，用来决定姐姐或哥哥。"""
