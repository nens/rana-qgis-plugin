FROM qgis/qgis:3.40
RUN apt-get update && apt-get install -y python3-pyqt5.qtwebsockets && apt-get clean
RUN apt-get update && apt-get install -y xvfb xauth

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11-utils \
    libgl1 \
    libglx-mesa0 \
    libgl1-mesa-dri \
    libxrender1 \
    libxext6 \
    fontconfig \
    dbus \
    mesa-utils

COPY requirements-dev.txt /root
COPY requirements-test.txt /root
RUN pip3 install -r /root/requirements-dev.txt --break-system-packages


ENV PYTHONPATH=/usr/share/qgis/python/:/usr/share/qgis/python/plugins:/usr/lib/python3/dist-packages/qgis:/usr/share/qgis/python/qgis:/root/.local/share/QGIS/QGIS3/profiles/default/python
ADD https://raw.githubusercontent.com/nens/nens-dependency-loader/refs/heads/main/dependencies.py /root/dependencies.py
RUN python3 /root/dependencies.py

RUN pip3 install -r /root/requirements-test.txt -c /root/constraints.txt --no-deps --upgrade --target /usr/share/qgis/python/plugins

WORKDIR /tests_directory
