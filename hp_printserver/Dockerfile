FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 LC_ALL=C
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod +x /usr/sbin/policy-rc.d \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       cups cups-client cups-filters printer-driver-foo2zjs \
       ghostscript avahi-daemon dbus python3 python3-cups ca-certificates psutils usbutils \
    && useradd --no-create-home --shell /usr/sbin/nologin --groups lpadmin printadmin \
    && usermod -a -G lpadmin root \
    && mkdir -p /opt/cups-default \
    && cp -a /etc/cups/. /opt/cups-default/ \
    && rm -rf /var/lib/apt/lists/*
COPY rootfs/ /
RUN test -x /usr/bin/foo2zjs \
    && test -x /usr/lib/cups/filter/foomatic-rip \
    && /usr/lib/cups/driver/foo2zjs list | grep -qi p1102w
CMD ["python3", "/opt/printserver/server.py"]
