FROM python:3.7-alpine
WORKDIR /ensa
VOLUME /ensa/files
RUN apk --update add libxml2-dev libxslt-dev libffi-dev gcc musl-dev libgcc openssl-dev curl
RUN apk add jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev g++ graphviz ghostscript-fonts
RUN pip3 install geotiler python-dateutil reportlab matplotlib graphviz pysqlcipher3
CMD ["python3", "./ensa.py"]
ADD ensa.py /ensa/
ADD source /ensa/source

