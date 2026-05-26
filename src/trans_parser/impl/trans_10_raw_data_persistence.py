import datetime
import json

from logger.logger_util import LoggerUtil
from model.model import transform_class_str, transform_flow_str
from trans_parser.task_base_executor import TaskBaseExecutor
from config.db_config import sql_to_df
from config.trans_config import MONTH_LIMIT
import pandas as pd
from trans_parser.impl.trans_single_portrait_label import TransSingleLabel

logger = LoggerUtil().logger(__name__)


class TransFlowRawData(TaskBaseExecutor):
    """
    将流水账户表和流水数据表落库
    updated_time_v1:20200707新增是否有新增数据字段,若有则有所有后续操作,若无,则无后续操作
    updated_time_v2:20200818添加commit的事务性,若发生错误则全部不提交
    """

    def __init__(self):
        super().__init__()
        self.df = None
        self.param = {}
        self.raw_list = []
        self.create_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')

    # def _mark_duplicate_data(self):
    #     sql = """select * from trans_flow where account_id in (select id from trans_account where account_name='%s'
    #         and id_card_no='%s' and account_no='%s' and bank='%s' and task_no='%s' and create_time > date_sub(now(), interval %d month))
    #         and repeated = 0 order by id desc""" % \
    #           (self.param.get('cusName'), self.param.get('idNo'), self.param.get('bankAccount'),
    #            self.param.get('bankName'), self.param.get('taskNo'), MONTH_LIMIT)
    #     df = sql_to_df(sql)
    #     # 重复标签打上默认值
    #     data = self.trans_data
    #     data['repeated'] = 0
    #     if df.shape[0] == 0:
    #         return data
    #     df['trans_time'] = pd.to_datetime(df['trans_time'])
    #     df['trans_date'] = df['trans_time'].apply(lambda x: x.date())
    #     data['trans_date'] = data['trans_time'].apply(lambda x: x.date())
    #     full_date_list = df.groupby('account_id')['trans_date'].agg({'min', 'max'})[['min', 'max']].values.tolist()
    #     merge_date_list = self.interval_merge(full_date_list)
    #     not_full_date_list = []
    #     full_date_string = "data[(data['trans_date'] < pd.to_datetime('%s').date()) | " % \
    #                        format(merge_date_list[0][0], '%Y-%m-%d')
    #     for i in range(len(merge_date_list) - 1):
    #         not_full_date_list.extend(merge_date_list[i])
    #         temp_str = "((data['trans_date'] > pd.to_datetime('%s').date()) & " \
    #                    "(data['trans_date'] < pd.to_datetime('%s').date())) | " % \
    #                    (format(merge_date_list[i][1], '%Y-%m-%d'), format(merge_date_list[i + 1][0], '%Y-%m-%d'))
    #         full_date_string += temp_str
    #     full_date_string += "(data['trans_date'] > pd.to_datetime('%s').date())]" % \
    #                         format(merge_date_list[-1][-1], '%Y-%m-%d')
    #     not_full_date_list.extend(merge_date_list[-1])
    #     full_date_df = eval(full_date_string)
    #     not_full_date_df = data[data['trans_date'].isin(not_full_date_list)]
    #     if not_full_date_df.shape[0] == 0:
    #         return full_date_df
    #     not_full_date_df1 = df[df['trans_date'].isin(not_full_date_list)]
    #     for row in not_full_date_df.itertuples():
    #         trans_date = getattr(row, 'trans_date')
    #         trans_amt = getattr(row, 'trans_amt')
    #         account_balance = getattr(row, 'account_balance', None)
    #         opponent_name = getattr(row, 'opponent_name')
    #         exist_df = not_full_date_df1[(not_full_date_df1['trans_amt'] == trans_amt) &
    #                                      (not_full_date_df1['trans_date'] == trans_date) &
    #                                      (not_full_date_df1['opponent_name'] == opponent_name)]
    #         if self.parse_context.parse_task.trans_flow_src_type in [1, '1']:
    #             exist_df = exist_df[exist_df['account_balance'] == account_balance]
    #         if exist_df.shape[0] > 0:
    #             not_full_date_df.drop(getattr(row, 'Index'), inplace=True)
    #     full_date_df = pd.concat([full_date_df, not_full_date_df], axis=0, sort=False)
    #     data.loc[~data.index.isin(full_date_df.index.tolist()), 'repeated'] = 1
    #     return

    def _mark_duplicate_data(self):
        # 1. 获取数据库中的历史数据（保持原有逻辑）
        sql = """select * from trans_flow where account_id in (select id from trans_account where account_name='%s'
                and id_card_no='%s' and account_no='%s' and bank='%s' and task_no='%s' and create_time > date_sub(now(), interval %d month))
                and repeated = 0 order by id desc""" % \
              (self.param.get('cusName'), self.param.get('idNo'), self.param.get('bankAccount'),
               self.param.get('bankName'), self.param.get('taskNo'), MONTH_LIMIT)
        existing_df = sql_to_df(sql)

        # 2. 向量化准备：统一日期格式
        existing_df['trans_time'] = pd.to_datetime(existing_df['trans_time'])
        existing_df['trans_date'] = existing_df['trans_time'].dt.date

        data = self.trans_data
        data['trans_date'] = pd.to_datetime(data['trans_time']).dt.date

        # 3. 初始化重复标记
        data['repeated'] = 0  # 默认为新数据

        # 4. 如果没有历史数据，直接返回
        if existing_df.empty:
            return data

        # 5. 【关键修复】安全的精确匹配
        key_cols = ['trans_date', 'trans_amt', 'opponent_name']

        if self.parse_context.parse_task.trans_flow_src_type in [1, '1']:
            # 条件性添加 account_balance，处理 NaN 情况
            # 创建一个辅助列，将 NaN 视为相同值进行匹配
            data['_balance_for_merge'] = data.get('account_balance', pd.Series([None] * len(data))).fillna(
                '__NULL__')
            existing_df['_balance_for_merge'] = existing_df.get('account_balance',
                                                                pd.Series([None] * len(existing_df))).fillna(
                '__NULL__')
            key_cols.append('_balance_for_merge')

        # 执行精确匹配（使用 indicator=True 以区分来源）
        merged_result = data.reset_index().merge(
            existing_df[key_cols + ['id']],  # 加上 'id' 作为存在标志
            on=key_cols,
            how='left',
            indicator=True
        )

        # 6. 【安全更新】基于合并结果更新 'repeated' 字段
        original_indices = merged_result.set_index('index').index
        data.loc[original_indices[merged_result['_merge'] == 'both'], 'repeated'] = 1

        # 7. 清理临时列
        if '_balance_for_merge' in data.columns:
            data.drop(columns=['_balance_for_merge'], inplace=True)

        return data


    @staticmethod
    def interval_merge(intervals):
        if len(intervals) <= 1:
            return intervals
        intervals.sort()
        result = [intervals[0]]
        for x in intervals[1:]:
            if x[0] >= result[-1][-1]:
                result.append(x)
            else:
                result[-1][-1] = max(result[-1][-1], x[-1])
        return result

    def _save_account_data(self):
        """
        将处理过后的流水数据的基本信息存入trans_account表,并将得到的account_id传入trans_flow表
        :return:
        """
        min_trans_time = self.df['trans_time'].min()
        max_trans_time = self.df['trans_time'].max()
        min_trans_time = datetime.datetime.strftime(min_trans_time, '%Y-%m-%d %H:%M:%S')
        max_trans_time = datetime.datetime.strftime(max_trans_time, '%Y-%m-%d %H:%M:%S')
        account_dict = dict()
        account_dict["out_req_no"] = self.parse_context.parse_task.out_req_no
        account_dict['account_name'] = self.param.get('cusName')
        account_dict['id_card_no'] = self.param.get('idNo')
        account_dict['id_type'] = self.param.get('idType')
        account_dict['bank'] = self.param.get('bankName')
        account_dict['account_no'] = self.param.get('bankAccount')
        account_dict['start_time'] = min_trans_time
        account_dict['end_time'] = max_trans_time
        account_dict['trans_flow_type'] = 1 if self.param.get('cusType') == 'PERSONAL' else 2
        account_dict['update_time'] = self.create_time
        account_dict['create_time'] = self.create_time
        account_dict['account_state'] = 1
        account_dict['task_no'] = self.param.get('taskNo')
        trans_account = transform_class_str(account_dict, 'TransAccount')
        # self.raw_list.append(trans_account)
        self.session.add(trans_account)
        self.session.commit()
        return trans_account.id

    def execute(self):
        # self.df = self.trans_data
        parse_task = self.parse_context.parse_task
        self.param = json.loads(parse_task.req_raw_data)
        query_data_array = self.param.get('queryData', [])

        account_id = self._save_account_data()
        self.parse_context.account_id = account_id
        self.df = self._mark_duplicate_data()
        logger.info("----打印日志  trans_data.shape: %s" % str(self.df.shape))
        # 原始数据列名
        col_list = ['trans_time', 'opponent_name', 'trans_amt', 'account_balance', 'currency',
                    'opponent_account_no', 'opponent_account_bank', 'trans_channel', 'trans_type',
                    'trans_use', 'remark', 'repeated', 'verif_label']
        varchar64_list = ['opponent_account_no', 'opponent_account_bank', 'trans_channel', 'trans_type']
        index = 0
        for row in self.df.itertuples():
            index = index + 1
            flow_dict = dict()
            flow_dict['account_id'] = account_id
            flow_dict['out_req_no'] = self.parse_context.parse_task.out_req_no
            flow_dict['file_id'] = self.param.get('fileId', None)
            for col in col_list:
                flow_dict[col] = getattr(row, col, None)
                if col in varchar64_list and pd.notna(flow_dict[col]):
                    flow_dict[col] = str(flow_dict[col])[:64]
            flow_dict['create_time'] = self.create_time
            flow_dict['update_time'] = self.create_time
            # 将原始数据落库
            # role = transform_class_str(flow_dict, 'TransFlow')
            self.raw_list.append(flow_dict)
        logger.info("save_raw_data begin")
        e = transform_flow_str(self.session, self.raw_list, 'TransFlow')
        # self.session.bulk_save_objects(self.raw_list)
        # self.session.add_all(self.raw_list)
        logger.info("save_raw_data end")
        if e is not None:
            err_msg = '导入数据库失败,失败原因:%s' % str(e)
            logger.error(err_msg)
            self.mark_err('导入数据库失败')
        else:
            # 重新从数据库中拉取不重复的数据，目的是获取flow_id
            sql = f"select * from trans_flow where account_id = {account_id} and repeated = 0"
            label_df = sql_to_df(sql)
            if label_df.shape[0] > 0:
                label_df['trans_flow_src_type'] = self.parse_context.parse_task.trans_flow_src_type
                label = TransSingleLabel(self.session, account_id, label_df, self.param.get('cusName'),
                                         self.param.get('cusType'), query_data_array)
                label.process()
