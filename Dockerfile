FROM python:3.7-alpine
WORKDIR /ensa
VOLUME /ensa/files
RUN apk --update add libxml2-dev libxslt-dev libffi-dev gcc musl-dev libgcc openssl-dev curl
RUN apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev g++
RUN pip3 install geotiler python-dateutil reportlab matplotlib
CMD ["python3", "./ensa.py"]
ADD ensa.py /ensa/
ADD source /ensa/source
#ADD source/__init__.py /ensa/source/
#ADD source/log.py /ensa/source/
#ADD source/lib.py /ensa/source/
#ADD source/ensa.py /ensa/source/
#ADD source/docs.py /ensa/source/
#ADD source/commands.py /ensa/source/
#ADD source/db.py /ensa/source/
#ADD source/pdf.py /ensa/source/
#ADD source/map.py /ensa/source/

