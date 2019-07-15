FROM python:3.6.8-slim-stretch

RUN groupadd -g 1000 docuser && \
    useradd -r -u 1000 -g docuser docuser

RUN apt-get update \
 && apt-get install make

RUN pip install 'Sphinx' \
                'sphinxprettysearchresults' \
                'sphinx_rtd_theme' \
                'sphinxcontrib-inheritance'

RUN mkdir /doc; chown -R docuser:docuser /doc

WORKDIR /doc

COPY ep /bin/ep
