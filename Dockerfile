FROM qgis/qgis:3.40
RUN apt-get update && apt-get install -y python3-pyqt5.qtwebsockets xvfb && apt-get clean
COPY requirements-dev.txt /root
COPY requirements-test.txt /root
RUN pip3 install -r /root/requirements-dev.txt --break-system-packages
RUN add-apt-repository ppa:mozillateam/ppa

RUN echo $' \n\
Package: * \n\
Pin: release o=LP-PPA-mozillateam \n\
Pin-Priority: 1001 \n\
Package: firefox \n\
Pin: version 1:1snap* \n\
Pin-Priority: -1 \n\
' | tee /etc/apt/preferences.d/mozilla-firefox

RUN apt-get update && apt-get install -y firefox && apt-get clean
RUN apt-get install -y xdg-utils

ENV PYTHONPATH=/usr/share/qgis/python/:/usr/share/qgis/python/plugins:/usr/lib/python3/dist-packages/qgis:/usr/share/qgis/python/qgis:/root/.local/share/QGIS/QGIS3/profiles/default/python
ADD https://raw.githubusercontent.com/nens/nens-dependency-loader/refs/heads/main/dependencies.py /root/dependencies.py
RUN python3 /root/dependencies.py

RUN pip3 install -r /root/requirements-test.txt -c /root/constraints.txt --no-deps --upgrade --target /usr/share/qgis/python/plugins

WORKDIR /tests_directory
