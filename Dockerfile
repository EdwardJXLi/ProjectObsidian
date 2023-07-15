FROM python:3.11.0-slim

RUN set -eux; useradd obsidian -d /server;
RUN apt-get update -y

COPY . /server
COPY .git/ /server/.git
WORKDIR /server

USER obsidian:obsidian

CMD [ "python3", "main.py", "-d" ]
