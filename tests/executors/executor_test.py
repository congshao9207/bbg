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
from src.parser.impl.trans_10_raw_data_persistence import TransFlowRawData


def test_trans_01():
    file_path = "../resource/农行流水.xlsx"
    executors = [TransFileLoadExecutor()]
    execute_common(file_path, executors)


def test_trans_02():
    file_path = "../resource/农行流水.xlsx"
    executors = [
        TransFileLoadExecutor(),
        TransDataStandardization()
    ]
    execute_common(file_path, executors)


def test_trans_03():
    file_path = "../resource/农行流水.xlsx"
    executors = [
        TransFileLoadExecutor(),
        TransDataStandardization(),
        TitleMatchExecutor()
    ]
    execute_common(file_path, executors)


def test_trans_04():
    file_path = r"C:\Users\Anrul\Desktop\标黄为错误项.xlsx"
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
    execute_common(file_path, executors)
