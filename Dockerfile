#FROM python:3.7-alpine
FROM python:3.7-slim-stretch
WORKDIR /ensa
VOLUME /ensa/files
ARG UID
RUN useradd -m -d /home/ensauser -u $UID  -s /bin/bash ensauser
USER ensauser
RUN apt-get update -y && apt-get -y install libsqlcipher-dev python3-pip
#RUN apk --update add libxml2-dev libxslt-dev libffi-dev gcc musl-dev libgcc openssl-dev curl
#RUN apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev g++
RUN pip3 install matplotlib
RUN pip3 install geotiler python-dateutil reportlab matplotlib graphviz pysqlcipher3
RUN apt-get -y install graphviz fonts-symbola vim
CMD ["python3", "./ensa"]
ADD ensa /ensa/
ADD source /ensa/source

