FROM python:3.11.0-slim

ENV PORT=25565
ENV NAME="Minecraft Server"
ENV MOTD="Python Server Implementation"

RUN apt-get update -y

COPY . /server
WORKDIR /server

CMD python3 main.py -d -v -p $PORT -n "$NAME" -m "$MOTD"
