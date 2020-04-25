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

ARG glassnode_api_key
ENV GLASSNODE_API_KEY=$glassnode_api_key

COPY . /app/

COPY $file /app/src
WORKDIR /app/src

CMD python3 alerts.py --verbose matrix-room --file "$file" --host "$host" --user "$user" --password "$password"
