from enum import Enum


class ResCodeEnum(Enum):
    SUCCESS = 0, " 成功"
    FAILED = 1, " 失败"
    EXCEPTION = 2, "异常"
    PROCESSING = 3, " 处理中"
    PARAM_ERROR = 10, " 参数错误"
    PARSE_FAILED = 20, " 解析失败"
    VALIDATION_FAILED = 21, " 校验失败"
    VERIFY_FAILED = 22, " 验真失败"
    FILE_DUPLICATION = 23, " 文件重复"
    PARAM_DUPLICATION = 24, " 参数重复"
    RECORD_NOT_EXISTS = 25, "记录不存在"
