# @Time : 1/21/22 11:19 AM 
# @Author : lixiaobo
# @File : db_config.py.py 
# @Software: PyCharm
import os

import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy_session import flask_scoped_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)

DB_CFG = {
    "host": os.getenv("DB_HOST", "192.168.2.21"),
    "port": os.getenv("DB_PORT", "3306"),
    "user": os.getenv("DB_USER", "root"),
    "pwd": os.getenv("DB_PWD", "magfin2021"),
    "db": os.getenv("DB_NAME", "trans_flow_taia")
}


conn_url = 'mysql+pymysql://%(user)s:%(pwd)s@%(host)s:%(port)s/%(db)s' % DB_CFG
engine = create_engine(conn_url, pool_pre_ping=True, pool_recycle=1800)


def init_connection(app):
    logger.info("conn_url:" + conn_url)

    app.config['SQLALCHEMY_DATABASE_URI'] = conn_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config["SQLALCHEMY_POOL_RECYCLE"] = 1800
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {'pool_pre_ping': True}

    session_factory = sessionmaker(bind=engine)
    flask_scoped_session(session_factory, app)

    return SQLAlchemy(app)


def sql_to_df(sql, index_col=None, coerce_float=True, params=None,
              parse_dates=None, columns=None, chunksize=None):
    df = pd.read_sql(sql, con=engine, index_col=index_col, coerce_float=coerce_float, params=params,
                     parse_dates=parse_dates, columns=columns, chunksize=chunksize)
    return df
