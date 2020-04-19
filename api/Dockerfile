FROM python:3.7

# Add software artifacts
WORKDIR /app
COPY requirements.txt /app

RUN apt-get update\
  && apt-get upgrade -y\
  && pip install -r requirements.txt

ARG glassnode_api_key
ENV GLASSNODE_API_KEY=$glassnode_api_key

HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://localhost:8000/docs || exit 1

COPY . /app/
WORKDIR /app/src
CMD python3 api.py
