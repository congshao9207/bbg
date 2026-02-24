# @Time : 4/14/22 1:24 PM 
# @Author : lixiaobo
# @File : pagination_serializer.py 
# @Software: PyCharm
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import DeclarativeMeta

from util.pagination import Pagination


directly_type = [str, int, Decimal]


class PaginationSerializer(object):
    def __init__(self, pagination):
        self.pagination = pagination

    def to_json(self):
        result = {}
        self.each_item(self.pagination, result)
        return result

    def each_item(self, d, result):
        if isinstance(d, Pagination):
            items = d.__dict__.items()
            for item in items:
                key = item[0]
                val = item[1]
                if isinstance(val, str) or isinstance(val, int):
                    result[key] = val
                elif isinstance(val, list):
                    new_data_list = []
                    for k in val:
                        new_data = {}
                        self.each_item(k, new_data)
                        new_data_list.append(new_data)
                    result[key] = new_data_list
        elif isinstance(d.__class__, DeclarativeMeta):
            for field in [x for x in dir(d) if not x.startswith('_') and x != 'metadata']:
                data = d.__getattribute__(field)
                if isinstance(data, int) or isinstance(data, str) or isinstance(data, Decimal):
                    result[field] = data
                elif isinstance(data, datetime):
                    result[field] = data.strftime("%Y-%m-%d %H:%M:%S")


