# @Time : 2/24/22 3:20 PM 
# @Author : lixiaobo
# @File : distributed_lock.py 
# @Software: PyCharm
import os
import uuid

from redis.lock import Lock

from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)
LOCK_SLEEP_MILL = 1000
LOCK_TIMEOUT_SECONDS = 60 * 10
LOCK_BLOCKING_TIMEOUT_SECONDS = 60
LOCK_KEY_PREFIX = "tpl_" + os.getenv("ENV", 'dev').lower() + "_"


class DistributedLockProxy(object):
    def __init__(self, redis_conn, resource_key, timeout: int = LOCK_TIMEOUT_SECONDS, sleep_time_mill=LOCK_SLEEP_MILL):
        sleep_time = sleep_time_mill / 1000
        self.token = str(uuid.uuid1())
        self.lock = Lock(redis_conn, LOCK_KEY_PREFIX + resource_key, timeout=timeout, sleep=sleep_time)

    def acquire(self, blocking_timeout: int = LOCK_BLOCKING_TIMEOUT_SECONDS):
        """ Acquire a redis distribution lock from redis connection with block mode
        """
        return self.lock.acquire(blocking=True, blocking_timeout=blocking_timeout, token=self.token)

    def acquire_no_block(self):
        """ Acquire a redis distribution lock from redis connection with No-block mode"""
        return self.lock.acquire(blocking=False, token=self.token)

    def release(self):
        """ Release the lock safely """
        try:
            self.lock.release()
        except Exception as e:
            # 其他异常记录日志
            logger.error(f"Unexpected error when releasing lock: {e}")
