FROM python:3.6.8-slim-stretch as build-doc
ARG VERSION
ARG TOKEN
WORKDIR /workspace
ENV USER=coog
RUN groupadd -g 1000 docuser ; \
    useradd -r -u 1000 -g docuser docuser ; \
    mkdir coog /doc; \ 
    chown -R docuser:docuser /doc ; \
    chown -R docuser:docuser /workspace ; \
    apt-get update ;\
    apt-get install -y make curl tar ;\
    pip install 'Sphinx' \
                'sphinxprettysearchresults' \
                'sphinx_rtd_theme' \
                'sphinxcontrib-inheritance';
USER docuser
RUN curl -SL https://api.github.com/repos/coopengo/coog/tarball/${VERSION}?access_token=${TOKEN} | tar xz --strip-components=1 -C ./coog; \
    cd /workspace/coog; \
    /workspace/coog/doc/build;

FROM node:8-alpine as build-sao-bench
LABEL maintainer="Coopengo <support@coopengo.com>"
ENV PATH="/workspace/bin:${PATH}"
ARG VERSION
ARG TOKEN
WORKDIR /workspace
RUN set -x; \
    apk add --no-cache \
      curl git ; \
    addgroup -S -g 1306 coog ; \
    adduser -S -u 1306 -G coog coog ; \
    chown coog:coog /workspace ; \
    npm i --unsafe-perm -g grunt-cli ; 
USER coog
RUN    set -x; \
    mkdir sao bench doc coog; \
    curl -SL https://api.github.com/repos/coopengo/sao/tarball/${VERSION}?access_token=${TOKEN} | tar xz  -C ./sao --strip-components=1; \
    curl -SL https://api.github.com/repos/coopengo/coog-bench/tarball/${VERSION}?access_token=${TOKEN} | tar xz  -C ./bench --strip-components=1; \
    cd /workspace/sao ; \
    /workspace/sao/build/ep ; \
    cd /workspace/bench ; \
    /workspace/bench/build/ep ; \
    ls -l /workspace/bench/* ; \
    ls -l /tmp/*


FROM node:8-alpine
LABEL maintainer="Coopengo <support@coopengo.com>"
WORKDIR /workspace
RUN set eux; \
    yarn global add serve ;
COPY build/static/serve.json /workspace/
COPY --from=build-sao-bench /workspace/sao/dist/ /workspace/sao/
COPY --from=build-sao-bench /tmp/coog-bench/ /workspace/bench/
COPY --from=build-doc /workspace/coog/doc/dist/html /workspace/doc/
USER root
CMD serve
EXPOSE 5000
