FROM python:3.7

# Add software artifacts
WORKDIR /app
COPY requirements.txt /app

RUN apt-get update\
  && apt-get upgrade -y\
  && pip install -r requirements.txt

ARG user
ENV user=$user
ARG host
ENV host=$host
ARG file
ENV file=$file
ARG password
ENV password=$password

COPY . /app/

WORKDIR /app/src

RUN chmod 0644 /app/docker_logger/logger.crontab
RUN crontab /app/docker_logger/logger.crontab

CMD cron -f
