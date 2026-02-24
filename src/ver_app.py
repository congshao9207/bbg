# @Time : 2/25/22 2:30 PM 
# @Author : lixiaobo
# @File : ver_app.py 
# @Software: PyCharm
import json

from flask import Blueprint
from flask_sqlalchemy_session import current_session

from model.model import TransAttachment
from util.ObjectSerializer import ObjectSerializer

ver_app = Blueprint('ver_app', __name__)


@ver_app.route("/orm_file_query")
def orm_file_query():
    info = current_session.query(TransAttachment).filter(TransAttachment.file_md_5 == "37824797297fdhw8sk").first()
    print("info:", info)
    return json.dumps(info, cls=ObjectSerializer)
