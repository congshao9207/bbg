# @Time : 5/10/22 5:26 PM 
# @Author : lixiaobo
# @File : trans_flow_list.py 
# @Software: PyCharm


class EntityIterator(object):
    def __init__(self, query):
        self.page = 0
        self.per_page = 20
        self.query = query

    def __next__(self):
        infos = self.query.offset(self.page*self.per_page)\
                .limit(self.per_page)\
                .all()
        self.page += 1
        if not infos or len(infos) == 0:
            raise StopIteration()
        return infos

    def __iter__(self):
        return self
