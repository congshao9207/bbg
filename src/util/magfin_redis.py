# @Time : 2/22/22 4:23 PM 
# @Author : lixiaobo
# @File : distributed_lock.py 
# @Software: PyCharm
import os

import redis

from config.trans_config import REDIS_HOST, REDIS_PORT, REDIS_MAX_CONN, REDIS_DB, REDIS_PWD
from util.simple_queue import SimpleMQ

redis_conn = redis.Redis(host=REDIS_HOST,
                         port=REDIS_PORT,
                         db=REDIS_DB,
                         password=REDIS_PWD,
                         decode_responses=True,
                         max_connections=int(REDIS_MAX_CONN))

trans_parse_queue = SimpleMQ(redis_conn, "trans_parser_" + os.getenv("ENV", 'dev').lower())

