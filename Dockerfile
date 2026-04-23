FROM qgis/qgis:3.40
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pyqt5.qtwebsockets \
    xvfb \
    xauth \
    x11-utils \
    x11vnc \
    fluxbox \
    imagemagick \
    libgl1 \
    libglx-mesa0 \
    libgl1-mesa-dri \
    libxrender1 \
    libxext6 \
    ffmpeg \
    fontconfig \
    dbus \
    mesa-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt /root
COPY requirements-test.txt /root
RUN pip3 install -r /root/requirements-dev.txt --break-system-packages

ADD https://raw.githubusercontent.com/nens/nens-dependency-loader/refs/heads/main/dependencies.py /root/dependencies.py
RUN python3 /root/dependencies.py
RUN pip3 install -r /root/requirements-test.txt -c /root/constraints.txt --no-deps --upgrade --target /usr/share/qgis/python/plugins

# Mimic qgis environment for testing
ENV PYTHONPATH=/usr/share/qgis/python/:/usr/share/qgis/python/plugins:/usr/lib/python3/dist-packages/qgis:/usr/share/qgis/python/qgis:/root/.local/share/QGIS/QGIS3/profiles/default/python

WORKDIR /tests_directory

COPY xvfb-startup.sh .
RUN sed -i 's/\r$//' xvfb-startup.sh
ARG RESOLUTION="1920x1080x24"
ENV XVFB_RES="${RESOLUTION}"
ARG XARGS=""
ENV XVFB_ARGS="${XARGS}"
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
ENTRYPOINT ["/bin/bash", "xvfb-startup.sh"]
