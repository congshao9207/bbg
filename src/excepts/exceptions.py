from flask import json
from flask import request
from werkzeug.exceptions import HTTPException


# 重写HTTPException异常中的get_body和get_headers方法,返回异常json格式
class APIException(HTTPException):

    def __init__(self, description=None, error_code=None):
        self.error_code = error_code
        super(APIException, self).__init__(description, None)

    # 重写父类的方法
    def get_body(self, environ, scope):
        return json.dumps(dict(
            code=self.code,
            name=self.name,
            error_code=self.error_code,
            requert=request.method + ">>" + request.url,
            description=self.get_description(environ)
        ))

    # 重写父类的方法
    def get_headers(self, environ, scope):
        return [('Content-Type', 'application/json')]


class ServerException(APIException):
    # 重写父类的属性
    code = 500
    description = "server error..."

    def __init__(self, description=None):
        super().__init__(description)
        self.description = description


class DataPreparedException(APIException):
    # 重写父类的属性
    code = 500
    description = "data prepared error..."

    def __init__(self, description=None):
        super().__init__(description)
        self.description = description


class DataExtractException(APIException):
    # 重写父类的属性
    code = 500
    description = "data extract error..."

    def __init__(self, description=None):
        super().__init__(description)
        self.description = description


class ParseException(Exception):
    def __init__(self, msg):
        self.msg = msg
