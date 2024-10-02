FROM qgis/qgis:3.38
RUN apt-get update && apt-get install -y python3-pyqt5.qtwebsockets && apt-get clean
RUN mkdir /tests_directory
COPY . /tests_directory
WORKDIR /tests_directory
RUN rana_qgis_plugin
