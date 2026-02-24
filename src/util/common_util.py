# @Time : 2/22/22 3:53 PM 
# @Author : lixiaobo
# @File : common_util.py 
# @Software: PyCharm
import hashlib


def calc_md5(*args):
    res = ""
    for arg in args:
        if arg:
            res = res + arg

    md5hash = hashlib.md5(res.encode("UTF-8"))
    return md5hash.hexdigest()
