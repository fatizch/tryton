FROM alpine:3.7 as build
LABEL maintainer="Coopengo <support@coopengo.com>"
ENV PATH="/workspace/bin:${PATH}"
WORKDIR /workspace
ARG VERSION
ARG TOKEN
RUN set -x; \
    apk add --no-cache \
      curl git; \
    mkdir coog trytond trytond-modules; \
    curl -SL https://api.github.com/repos/coopengo/coog/tarball/${VERSION}?access_token=${TOKEN} | tar xz  -C ./coog --strip-components=1; \
    curl -SL https://api.github.com/repos/coopengo/trytond/tarball/${VERSION}?access_token=${TOKEN} | tar xz  -C ./trytond --strip-components=1; \
#   curl -SL https://api.github.com/repos/coopengo/trytond-modules/tarball/${VERSION}?access_token=${TOKEN} | tar xz --strip-components=1 -C ./trytond-modules; \
    git clone https://x-token-auth:${TOKEN}@github.com/coopengo/trytond-modules.git -b ${VERSION}; \
    cd trytond-modules; \
    sed -i -e "s#git@github.com:#https://x-token-auth:${TOKEN}@github.com/#g" .gitmodules; \
    git submodule update --init; \
    find . | grep .git | xargs rm -rf \;

FROM  alpine:3.7
LABEL maintainer="Coopengo <support@coopengo.com>"
WORKDIR /workspace
COPY --from=build /workspace/coog  /workspace/coog
COPY --from=build /workspace/trytond  /workspace/trytond
COPY --from=build /workspace/trytond-modules  /workspace/trytond-modules
COPY build/ep /workspace/bin/ep
COPY build/requirements.txt /workspace/requirements.txt
RUN set -eux; \
    addgroup -g 1000 coog; \
    adduser -u 1000 -G coog -s /bin/sh -D coog; \
    apk add --no-cache \
        tar curl bash python3 redis graphviz libmagic coreutils \
        py3-lxml py3-psycopg2 py3-redis py3-ldap3 uwsgi-python3 vim git ; \
    ln -s /usr/bin/python3 /usr/bin/python; \
    ln -s /workspace/trytond/bin/trytond /workspace/bin/trytond; \
    ln -s /workspace/trytond/bin/trytond-admin /workspace/bin/trytond-admin; \
    ln -s /workspace/trytond/bin/trytond-cron /workspace/bin/trytond-cron; \
    /workspace/bin/ep link; \
    chown coog /workspace -R; \
    pip3 install -r /workspace/requirements.txt --no-cache-dir; \
    rm -rf /root/.cache; \
    find / -name "__pycache__" -prune -exec rm -rf {} \;
USER coog
ENV PATH="/workspace/bin:${PATH}"
ENTRYPOINT ["ep"]
EXPOSE 8000
