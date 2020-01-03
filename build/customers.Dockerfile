ARG VERSION
FROM  alpine:3.7 as build
LABEL maintainer="Coopengo <support@coopengo.com>"
ARG TOKEN
ARG CUSTOMERS_TAG
ARG CUSTOMERS
WORKDIR /workspace
RUN set -x; \
    apk add --no-cache \
        tar curl ; \
    mkdir customers; \
    curl -SL https://api.github.com/repos/coopengo/customers/tarball/${CUSTOMERS}-${CUSTOMERS_TAG}?access_token=${TOKEN} | tar xz  -C ./customers --strip-components=1;

FROM  coopengo/coog:${VERSION}
COPY --from=build /workspace/customers  /workspace/customers
RUN set -eux; \
    ep link;