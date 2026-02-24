FROM registry.cn-shanghai.aliyuncs.com/transformer/magfin_python_base:0.0.1

COPY . /usr/src/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONIOENCODING utf-8
EXPOSE 8011
ENV PYTHONIOENCODING utf-8

CMD ["gunicorn", "--workers=5", "--bind=0.0.0.0:8011", "app:app", "-t=600"]

# CMD ["uwsgi", "--ini", "uwsgi.ini"]
