# @Time : 2/21/22 2:11 PM
# @Author : lixiaobo
# @File : RespEntity.py
# @Software: PyCharm
import json

from flask import jsonify

from util.string_util import is_empty


class RespEntity (object):
    def __init__(self):
        self.resCode = 0
        self.resMsg = "成功"
        self.data = {}
        self.stats = {}

    def ok(self, data=None):
        self.data = data
        return json.dumps(self)

    @staticmethod
    def response(res_code, res_msg, data=None):
        resp = RespEntity()
        resp.resCode = res_code
        resp.resMsg = res_msg
        resp.data = data
        return jsonify(resp.__pack())

    @staticmethod
    def with_res_enum(res_enum, msg=None, data=None, stats=None):
        resp = RespEntity()
        resp.resCode = res_enum.value[0]
        resp.resMsg = res_enum.value[1] if is_empty(msg) else msg
        resp.data = data
        resp.stats = stats
        return jsonify(resp.__pack())

    def __pack(self):
        return {
            "resCode": self.resCode,
            "resMsg": self.resMsg,
            "data": self.data,
            'stats': self.stats
        }

