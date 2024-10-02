FROM qgis/qgis:3.38
RUN apt-get update && apt-get install -y python3-pyqt5.qtwebsockets && apt-get clean
RUN mkdir /tests_directory
COPY . /tests_directory
RUN qgis_setup.sh rana_qgis_plugin
WORKDIR /tests_directory
