# @Time : 2/24/22 11:43 AM 
# @Author : lixiaobo
# @File : trans_03_data_verify_executor.py 
# @Software: PyCharm
from trans_parser.task_base_executor import TaskBaseExecutor


# 不允许， 方法需要写入class内部（util类型的方法除外）
def method_name():
    pass


class ExampleExecutor(TaskBaseExecutor):
    def __init__(self):
        super().__init__()

    def execute(self):
        raise NotImplementedError()
        #  获取df
        # df = self.trans_data

        # 处理df
        # try:
        #    pass
        # except Exception as e:
        #    如果处理异常
        #    self.mark_err("xxxxx" + str(e))

        # 如果要中断处理，需要调用
        # self.mark_err("xxxxx")
        # return

        # 如果要获取是否需要纠偏：
        # rectify = self.parse_context.trans_task.rectify

        # 结果保存
        # self.trans_data = df

