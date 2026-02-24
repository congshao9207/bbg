# @Time : 3/3/22 5:36 PM 
# @Author : lixiaobo
# @File : builder.py.py 
# @Software: PyCharm
from src.component.parse_context import ParseContext
from model.model import TransParseTask


def execute_common(file_path, executors):
    tpt = TransParseTask()
    tpt.rectify = 1

    pc = ParseContext(tpt, file_path)
    for executor in executors:
        executor.init(file_path, None, pc)
        executor.execute()
        df = executor.trans_data

    assert len(df) > 0
