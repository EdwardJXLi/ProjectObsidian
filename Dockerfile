FROM python:3.11.0-slim

RUN apt-get update -y

COPY . /server
WORKDIR /server

CMD [ "python3", "main.py", "-d" ]
