# @Time : 2/23/22 1:56 PM 
# @Author : lixiaobo
# @File : __init__.py.py 
# @Software: PyCharm
import time

import pandas as pd
import random

# 定义常量
BIG_IN_OUT_EXCEPT = "冲正|抹账|冲销"  # 与您的代码中保持一致
OPPONENT_NAMES_POOL = ["阿里巴巴", "腾讯科技", "华为技术", "小米集团", "京东物流", "美团外卖", "字节跳动", "百度在线",
                       "网易公司", "携程旅行"]
TRANS_CHANNELS_POOL = ["网银转账", "手机银行", "ATM机", "柜台", "第三方支付", "POS机消费"]
TRANS_USES_POOL = ["货款", "服务费", "退款", "押金", "差旅费", "办公用品", "工资"]


def generate_sample_data():
    """生成包含冲正数据的示例数据集"""
    data = []
    # 生成 94 条普通数据
    for i in range(94):
        data.append({
            "opponent_name": random.choice(OPPONENT_NAMES_POOL),
            "trans_amt": round(random.uniform(-5000, 5000), 2),
            "trans_channel": random.choice(TRANS_CHANNELS_POOL),
            "trans_use": random.choice(TRANS_USES_POOL),
            "remark": f"日常交易{i}"
        })

    # 生成 6 条冲正数据 (形成 3 对)
    # 冲正数据的特点是：对手方相同，金额相反，备注中包含 "冲正" 关键词
    reversal_pairs_info = [
        {
            "opponent": "腾讯科技",
            "amount_positive": 1234.56,
            "channel": "手机银行",
            "use": "服务费"
        },
        {
            "opponent": "美团外卖",
            "amount_positive": 789.10,
            "channel": "第三方支付",
            "use": "退款"
        },
        {
            "opponent": "字节跳动",
            "amount_positive": 555.55,
            "channel": "网银转账",
            "use": "货款"
        }
    ]

    for info in reversal_pairs_info:
        # 正数交易
        positive_record = {
            "opponent_name": info["opponent"],
            "trans_amt": info["amount_positive"],
            "trans_channel": info["channel"],
            "trans_use": info["use"],
            "remark": f"正常交易，原因：{random.choice(['服务费', '货款', '退款'])}"
        }
        # 冲正交易 (负数，带关键词)
        negative_record = {
            "opponent_name": info["opponent"],
            "trans_amt": -info["amount_positive"],
            "trans_channel": info["channel"],
            "trans_use": info["use"],
            "remark": f"冲正交易，原因：{random.choice(['冲正', '抹账', '冲销'])}"
        }

        data.append(positive_record)
        data.append(negative_record)

    # 打乱数据顺序，使其看起来更随机
    random.shuffle(data)

    return pd.DataFrame(data)


# --- 执行生成 ---
# df_with_reversals = generate_sample_data()
# df_with_reversals.to_excel("test.xlsx")

def _choose_index():
    """
    剔除冲正、抹账、冲销相关数据
    """
    df = pd.read_excel("test.xlsx")
    temp_df = df.copy()
    concat_list = ['trans_channel', 'trans_use', 'remark']
    temp_df[concat_list] = temp_df[concat_list].fillna('').astype(str)
    temp_df['text'] = temp_df['trans_channel'] + temp_df['trans_use'] + temp_df['remark']
    index_list1 = temp_df[temp_df.text.str.contains(BIG_IN_OUT_EXCEPT)].index.tolist()
    to_drop = set()
    for idx in range(len(index_list1)):
        row = temp_df.loc[index_list1[idx]]
        matched = temp_df[
            (temp_df['opponent_name'] == row['opponent_name']) &
            (temp_df['trans_amt'] == -row['trans_amt'])
            ].index.tolist()
        # # 可选：排除自己（如果存在自反情况，一般不会）
        matched = [i for i in matched if i != idx]
        to_drop.add(index_list1[idx])
        if matched:
            # 成对删除：只删第一个匹配项（避免多删）
            try:
                to_drop.add(matched[0])
            except Exception as e:
                raise Exception(e)
    df = df.drop(index=list(to_drop)).reset_index(drop=True)
    df.to_excel("test1.xlsx")
