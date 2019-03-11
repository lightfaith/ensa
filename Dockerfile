FROM python:3.7-alpine
WORKDIR /ensa
VOLUME /ensa/files
RUN pip3 install python-dateutil
CMD ["python3", "./ensa.py"]
ADD ensa.py /ensa/
#ADD source /ensa/source
ADD source/__init__.py /ensa/source/
ADD source/log.py /ensa/source/
ADD source/lib.py /ensa/source/
ADD source/ensa.py /ensa/source/
ADD source/docs.py /ensa/source/
ADD source/commands.py /ensa/source/
ADD source/db.py /ensa/source/

