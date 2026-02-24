# @Time : 1/20/22 7:08 PM 
# @Author : lixiaobo
# @File : ObjectSerializer.py 
# @Software: PyCharm
import json

from sqlalchemy.orm import DeclarativeMeta


class ObjectSerializer(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                fields[field] = data
            return fields

        return json.JSONEncoder.default(self, obj)
