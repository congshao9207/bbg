FROM python:3.8
RUN apt-get install tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone
ENV TZ Asia/Shanghai

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY requirements.txt /usr/src/app

RUN pip3 install --no-cache-dir -r requirements.txt
ENV PYTHONUNBUFFERED 1