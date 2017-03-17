FROM python:2-slim
MAINTAINER Coopengo <support@coopengo.com>

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libldap2-dev \
        libsasl2-dev \
        libreoffice-writer \
        unoconv \
        redis-tools \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install \
        pyflakes \
        dateutils \
        num2words \
        lxml \
        python-sql \
        psycopg2 \
        polib \
        Genshi \
        relatorio \
        pydot \
        pyparsing \
        python-stdnum \
        unidecode \
        intervaltree \
        filelock \
        wrapt \
        werkzeug \
        simpleeval \
        ldap3 \
        requests \
        raven \
        redis \
        hiredis \
        msgpack-python \
        numpy \
        scipy \
        uwsgi \
        "celery<4" \
        rq \
    && rm -rf /root/.cache

RUN mkdir /coog && mkdir /coog/data
COPY . /coog/

RUN ln -s /coog/trytond/bin/trytond /usr/local/bin
RUN ln -s /coog/trytond/bin/trytond-admin /usr/local/bin
RUN ln -s /coog/trytond/bin/trytond-cron /usr/local/bin
RUN ln -s /coog/coog/bin/docker/ep /usr/local/bin/ep
RUN ep link

VOLUME ["/coog/sao", "/coog/coog-bench"]

ENTRYPOINT ["ep"]
EXPOSE 8000
