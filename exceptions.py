class BaseException(Exception):
    pass

class NotEnoughCreditsException(BaseException):
    pass

class FailedToGenerateImageException(BaseException):
    pass

class UserNotActiveException(BaseException):
    pass

class FailedToGenerateStoryException(BaseException):
    pass

class FailedToGenerateChatException(BaseException):
    pass

class DailyStoryLimitExceededException(BaseException):
    pass

class DailyChatLimitExceededException(BaseException):
    pass
