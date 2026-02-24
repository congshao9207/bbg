# @Time : 2/22/22 7:12 PM 
# @Author : lixiaobo
# @File : simple_queue.py 
# @Software: PyCharm

from redis import Redis
import secrets
import string
from typing import List, Optional


class SimpleMQ:
    """Defines a simple FIFO message queue using Redis"""

    REDIS_KEY_PREFIX = "REDIS_SIMPLE_MQ"
    RANDOM_NAME_LENGTH = 16

    def __init__(self, conn: Redis, name: str = None) -> None:
        """Connects to a queue on Redis with the given name. Will create the queue if ti does not exist.

        Args:
        - conn: Redis connection object, e.g. conn = Redis()
        - name: optional name of this queue. If not defined a random ID will be generated.
        """

        if not isinstance(conn, Redis):
            raise TypeError("conn must be of type Redis")

        self._conn = conn
        if name is None:
            self._name = "".join(
                [
                    secrets.choice(string.ascii_lowercase + string.digits)
                    for _ in range(self.RANDOM_NAME_LENGTH)
                ]
            )
        else:
            self._name = str(name)

    def _redis_key(self) -> str:
        """returns the full key used to locate this queue on redis"""
        return "{}_{}".format(self.REDIS_KEY_PREFIX, self.name)

    @property
    def conn(self) -> Redis:
        return self._conn

    @property
    def name(self) -> str:
        return self._name

    def size(self) -> int:
        """return current number of messages in the queue"""
        return int(self.conn.llen(self._redis_key()))

    def clear(self) -> int:
        """deletes all messages from the given queue.
        Returns number of cleared messages.
        """
        total = 0
        while True:
            message = self.dequeue()
            if message is None:
                break
            else:
                total += 1

        return total

    def enqueue(self, message: str) -> int:
        """enqueue one message int the queue

        returns size of the queue after enqueuing
        """
        return self.conn.rpush(self._redis_key(), str(message))

    def enqueue_bulk(self, messages: List[str]) -> int:
        """enqueue a list of messages into the queue at once

        returns size of the queue after enqueuing
        """
        queue_size = None
        for x in list(messages):
            queue_size = self.enqueue(x)

        return queue_size

    def dequeue(self) -> Optional[str]:
        """dequeue one message from the queue. returns None if empty"""
        value = self.conn.lpop(self._redis_key())
        if value is not None:
            return value
        else:
            return None

    def dequeue_bulk(self, max: int = None) -> List[str]:
        """dequeue a list of message from the queue.

        return no more than max message from queue
        returns all messages int the queue if max is not specified
        returns an empty list if queue is empty
        """

        if max is not None and int(max) < 0:
            raise ValueError("max can not be negative")

        messages = list()
        n = 0
        while True:
            if max is not None and n == int(max):
                break
            else:
                n += 1
                x = self.dequeue()
                if x is None:
                    break
                else:
                    messages.append(x)

        return messages
