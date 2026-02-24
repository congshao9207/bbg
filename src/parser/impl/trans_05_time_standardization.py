
from config.trans_config import DTTIME_PATTERN, TIME_PATTERN, DATE_PATTERN, TIME_S_PATTERN, SHORT_DATE_PATTERN
import pandas as pd
import datetime
import re

from parser.task_base_executor import TaskBaseExecutor


def dttime_apply(time):
    # 首位是'2',形如'2020-01-01 05:02:04',末尾加上'000000'是为了防止出现秒钟缺失情况
    try:
        temp = format(pd.to_datetime(re.sub(r'[\\-]', '/', str(time))), '%Y%m%d%H%M%S')
    except (ValueError, TypeError, OverflowError):
        temp = ''.join([_ for _ in time if _.isdigit()])
    result = None
    if len(temp) <= 4:
        return
    if temp[0] == '2':
        temp += '000000'
        temp = temp[:14]
        try:
            if re.match(DTTIME_PATTERN, temp):
                result = datetime.datetime.strptime(temp, '%Y%m%d%H%M%S')
        except (ValueError, TypeError, OverflowError):
            result = None
    # 首位是'4',形如'43562.125',表示'2019-04-07 03:00:00'
    elif temp[0] == '4':
        date = datetime.datetime(1900, 1, 1) + datetime.timedelta(days=int(temp[:5]) - 2)
        date_str = datetime.datetime.strftime(date, '%Y%m%d')
        time_str = '000000'
        if len(temp) > 5:
            time_value = int(temp[5:]) / 10 ** (len(temp) - 5)
            if time != 0:
                time_str = str(int(time_value * 24)).rjust(2, '0') + \
                           str(int(time_value * 1440) % 60).rjust(2, '0') + \
                           str(int(time_value * 86400) % 60).rjust(2, '0')
        result = datetime.datetime.strptime(date_str + time_str, '%Y%m%d%H%M%S')
    return result


class TransTimeStandardization(TaskBaseExecutor):
    """
    将流水文件中交易时间标准化
    author:汪腾飞
    created_time:20200630
    updated_time_v1:20200819找到时间列后不再进行排序,排序放到余额验真里面进行,且若交易时间列存在空值则用上面的值填充,
            不再删除交易时间列含有部门空值的情况
    updated_time_v2:20200911,导入间隔校验时间扩充为45天,相应的导入失败提示也更改为45天
    updated_time_v3:20201125,导入间隔,查询间隔,交易间隔现在都是可配置的,修改起始截止时间校验逻辑
    updated_time_v4:20201223,时间日期格式和日期格式匹配加入了字符串为空的判断，之后不会再出现下标越界的提示
    updated_time_v5:20220420,新增智能删除功能
    """

    def __init__(self):
        super().__init__()
        self.df = None
        self.title_param = {}
        self.time_col = None
        self.acc_time_col = None
        self.query_start = None
        self.query_end = None
        self.basic_status = True
        self.sort_list = []  # 需要排序的列

    def _query_date_transform(self):
        try:
            self.query_start = dttime_apply(self.title_param.get('start_date'))
            self.query_end = dttime_apply(self.title_param.get('end_date'))
        except (ValueError, TypeError):
            self.query_start = None
            self.query_end = None

    def _match_time_head(self, column, pattern, number):
        """
        匹配时间列的前20行(最多)，如果超过70%的行满足对应的模式，则认为该模式匹配成功
        :param column: 列名
        :param pattern: 正则表达式
        :param number: 匹配的数字位数
        :return:
        """
        sample = list(self.df[column][:20])
        cnt = len(sample)
        for x in sample:
            try:
                if re.search(r'[\\/-]', x):
                    x = format(pd.to_datetime(re.sub(r'[\\-]', '/', str(x))), '%Y%m%d%H%M%S')
                else:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                if type(x) == float:
                    x = str(int(x))
                else:
                    x = str(x)
            y = [_ for _ in x if _.isdigit()]
            z = ''.join(y)[:number]
            if number == 6 or number == 4:
                z = z.rjust(number, '0')
            # 一旦出现不匹配的时间格式或者时间列的时间全都是0，则视为该行不匹配
            if re.match(pattern, z) is None or (number == 14 and z[-6:] == '000000'):
                cnt -= 1
        # 匹配比例超过70%返回True，否则False
        return cnt / len(sample) >= 0.7

    @staticmethod
    def _date_apply(time):
        try:
            temp = format(pd.to_datetime(re.sub(r'[\\-]', '/', str(time))), '%Y%m%d')
        except (ValueError, TypeError, OverflowError):
            temp = ''.join([_ for _ in time if _.isdigit()])
        if len(temp) == 0:
            return ''
        if temp[0] == '2':
            result = temp[:8]
        elif temp[0] == '4':
            date = datetime.datetime(1900, 1, 1) + datetime.timedelta(days=int(temp[:5]) - 2)
            result = datetime.datetime.strftime(date, '%Y%m%d')
        else:
            # 若不满足格式，则将result赋值为空字符串
            # raise ValueError("交易日期列有不符合格式的值t002")
            result = ''
        return result

    @staticmethod
    def _time_apply(time):
        if ':' in time or '：' in time:
            time_list = time.split('.')
            if len(time_list[0]) >= 8:
                time = time_list[0]
            temp = '000000' + ''.join([_ for _ in time if _.isdigit()])
            result = temp[-6:]
        elif '.' in time:
            try:
                temp = float(time)
            except ValueError:
                # 若不是浮点数，则赋值为0
                # raise ValueError("交易时间列有不符合格式的值t003")
                temp = 0
            if temp < 1:
                result = str(int(temp * 24)).rjust(2, '0') + str(int(temp * 1440) % 60).rjust(2, '0') + str(
                    int(temp * 86400) % 60).rjust(2, '0')
            else:
                result = str(int(temp)).rjust(6, '0')
        elif len(time) >= 1:
            temp = '000000' + time.split('.')[0]
            result = temp[-6:]
        else:
            result = '000000'
        if re.match(TIME_PATTERN, result) is None:
            result = '000000'
        return result

    def _one_col_match(self, col):
        self.sort_list = [col]
        length = self.df.shape[0]
        short_date_pat = re.compile(SHORT_DATE_PATTERN)
        if self._match_time_head(col, short_date_pat, 6):
            self.df[col] = self.df[col].astype(str).apply(lambda x: '20' + x)
        self.df['trans_time'] = self.df[col].astype(str).apply(dttime_apply)
        # 20240920 新增判断，是否存在交易时间列为空的情况，若存在，判断是否存在不包含中文和英文的行，若存在，将要删除的行，做提示
        if self.df['trans_time'].isnull().sum() > 0:
            if self.df.loc[(~self.df[col].astype(str).str.contains(r'[\u4e00-\u9fa5]+')) &
                           (~self.df[col].astype(str).str.contains(r'[a-zA-Z]+')) &
                           (pd.isna(self.df['trans_time']))].shape[0] > 0:
                self.trans_date_delete_status()
        self.trans_data = self.df[pd.notna(self.df['trans_time'])]
        if self.trans_data.shape[0] / length < 0.7:
            raise ValueError("无法找到交易日期列")
        self.trans_data.reset_index(drop=True, inplace=True)

    def _multi_col_match(self, res):
        dttime_pat = re.compile(DTTIME_PATTERN)
        date_pat = re.compile(DATE_PATTERN)
        short_date_pat = re.compile(SHORT_DATE_PATTERN)
        time_pat = re.compile(TIME_PATTERN)
        time_s_pat = re.compile(TIME_S_PATTERN)
        dttime_status = False
        short_status = False
        date_col = ''
        time_col = ''
        for col in res:
            if self._match_time_head(col, dttime_pat, 14) and not dttime_status:
                self.df['trans_time'] = self.df[col].astype(str).apply(dttime_apply)
                self.sort_list = [col]
                dttime_status = True
        if not dttime_status:
            for col in res:
                if self._match_time_head(col, date_pat, 8):
                    date_col = col
                    self.df[date_col] = self.df[date_col].astype(str).apply(self._date_apply)
                    self.sort_list.append(date_col)
                    res.remove(col)
                    break
                elif self._match_time_head(col, short_date_pat, 6):
                    date_col = col
                    self.df['short_date'] = self.df[col]
                    self.df[date_col] = \
                        self.df[date_col].astype(str).apply(lambda x: '20' + x).apply(self._date_apply)
                    self.sort_list.append(date_col)
                    res.remove(col)
                    short_status = True
                    break
            for col in res:
                # 如果已经找到日期列，且在寻找时间列时，时间列与日期列完全一致，则不考虑该列
                if date_col != '' and list(self.df[date_col].astype(str)[:10]) == list(self.df[col].astype(str)[:10]):
                    continue
                if short_status and list(self.df['short_date'].astype(str)[:10]) == list(self.df[col].astype(str)[:10]):
                    continue
                if self._match_time_head(col, time_pat, 6) or self._match_time_head(col, time_s_pat, 4):
                    time_col = col
                    self.df[time_col] = self.df[time_col].fillna(0).astype(str).apply(self._time_apply)
                    self.sort_list.append(time_col)
                    break
            if date_col != '' and time_col != '':
                self.df['trans_time'] = self.df[date_col] + self.df[time_col]
                self.df['trans_time'] = self.df['trans_time'].apply(dttime_apply)
            elif date_col != '' and time_col == '':
                self.df['trans_time'] = self.df[date_col].apply(dttime_apply)
        length = self.df.shape[0]
        # 20240920 新增判断，是否存在交易时间列为空的情况，若存在，判断是否存在不包含中文和英文的行，若存在，将要删除的行，做提示
        if self.df['trans_time'].isnull().sum() > 0:
            if self.df.loc[(~self.df[res[0]].astype(str).str.contains(r'[\u4e00-\u9fa5]+')) &
                           (~self.df[res[0]].astype(str).str.contains(r'[a-zA-Z]+')) &
                           (pd.isna(self.df['trans_time']))].shape[0] > 0:
                self.trans_date_delete_status()
        self.trans_data = self.df[pd.notna(self.df['trans_time'])]
        if self.trans_data.shape[0] / length < 0.7:
            raise ValueError("无法找到交易日期列")
        self.trans_data.reset_index(drop=True, inplace=True)

    def execute(self):
        self.df = self.trans_data
        self.time_col = self.col_mapping()['time_col']

        for col in self.time_col:
            self.df[col] = self.df[col].apply(lambda x: str(x).replace('O', '0').replace('l', '1')
                                              if x != '' else '000000')
        self.df['trans_time'] = None
        res = self.time_col
        length = len(res)
        if length == 0:
            self.mark_err("解析失败：找不到时间列")
            return
        try:
            # 初始化
            self.trans_date_delete_status_init()
            if length == 1:
                self._one_col_match(res[0])
            else:
                self._multi_col_match(res)
        except Exception as e1:
            self.mark_err("解析失败：" + str(e1))
        self.attach_context('sort_list', self.sort_list)

