FROM joeystevens00/mormo:api

WORKDIR /tmp/alerts
ARG file
ENV file=$file
ARG host
ENV host=$host

COPY $file /tmp/alerts
COPY . /tmp/alerts

CMD bash entrypoint.sh
