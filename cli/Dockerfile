FROM python:3.7

# Add software artifacts
WORKDIR /app
COPY requirements.txt /app

RUN apt-get update\
  && apt-get upgrade -y\
  && pip install -r requirements.txt

ARG user
ENV MATRIX_USER=$user
ARG host
ENV MATRIX_HOST=$host
ARG file
ENV file=$file
ARG password
ENV MATRIX_PASSWORD=$password

ARG glassnode_api_key
ENV GLASSNODE_API_KEY=$glassnode_api_key

COPY . /app/

COPY $file /app/src
WORKDIR /app/src

ENV MATRIX_PASSWORD=$password

CMD python3 alerts.py --verbose matrix-room --file "$file" --host "$host" --user "$user"
