# @Time : 3/3/22 5:17 PM 
# @Author : lixiaobo
# @File : trans_01_file_load_executor_test.py.py 
# @Software: PyCharm
from executors.builder import execute_common
from src.parser.impl.trans_01_file_load_executor import TransFileLoadExecutor
from src.parser.impl.trans_02_data_standardization import TransDataStandardization
from src.parser.impl.trans_03_rectify_executor import RectifyExecutor
from src.parser.impl.trans_04_title_match_executor import TitleMatchExecutor
from src.parser.impl.trans_05_time_standardization import TransTimeStandardization
from src.parser.impl.trans_06_amount_standardization import TransAmountStandardization
from src.parser.impl.trans_07_opponent_info_standardization import TransOpponentInfoStandardization
from src.parser.impl.trans_08_other_info_standardization import TransOtherInfoStandardization
from src.parser.impl.trans_09_verify_authenticity_executor import VerifyAuthenticityExecutor
# from src.parser.impl.trans_10_raw_data_persistence import TransFlowRawData


# def test_trans_01():
#     file_path = "../resource/农行流水.xlsx"
#     executors = [TransFileLoadExecutor()]
#     execute_common(file_path, executors)
#
#
# def test_trans_02():
#     file_path = "../resource/农行流水.xlsx"
#     executors = [
#         TransFileLoadExecutor(),
#         TransDataStandardization()
#     ]
#     execute_common(file_path, executors)
#
#
# def test_trans_03():
#     file_path = "../resource/农行流水.xlsx"
#     executors = [
#         TransFileLoadExecutor(),
#         TransDataStandardization(),
#         TitleMatchExecutor()
#     ]
#     execute_common(file_path, executors)


def test_trans_04():
    file_path = r"TK1003018541336788992_1772619227593.xlsx"
    executors = [
        TransFileLoadExecutor(),
        TransDataStandardization(),
        RectifyExecutor(),
        TitleMatchExecutor(),
        TransTimeStandardization(),
        TransAmountStandardization(),
        TransOpponentInfoStandardization(),
        TransOtherInfoStandardization(),
        VerifyAuthenticityExecutor(),
        # TransFlowRawData()
    ]
    import time
    start_time = time.time()
    execute_common(file_path, executors)
    print(time.time() - start_time)


def test_perf():
    """性能测试，逐个执行器计时"""
    file_path = r"hnls111.xlsx"
    import time
    executors = [
        (TransFileLoadExecutor(), 'TransFileLoadExecutor'),
        (TransDataStandardization(), 'TransDataStandardization'),
        (RectifyExecutor(), 'RectifyExecutor'),
        (TitleMatchExecutor(), 'TitleMatchExecutor'),
        (TransTimeStandardization(), 'TransTimeStandardization'),
        (TransAmountStandardization(), 'TransAmountStandardization'),
        (TransOpponentInfoStandardization(), 'TransOpponentInfoStandardization'),
        (TransOtherInfoStandardization(), 'TransOtherInfoStandardization'),
        (VerifyAuthenticityExecutor(), 'VerifyAuthenticityExecutor'),
    ]
    from src.component.parse_context import ParseContext
    from src.model.model import TransParseTask
    tpt = TransParseTask()
    tpt.rectify = 1
    pc = ParseContext(tpt, file_path)
    for executor, name in executors:
        start = time.time()
        executor.init(file_path, None, pc)
        executor.execute()
        df = executor.trans_data
        elapsed = time.time() - start
        print(f'{name}: {elapsed:.2f}s')
        # 更新 parse_context 中的 trans_data 供下一个执行器使用
        pc.trans_data = df
    print(f'总行数: {len(df)}')
