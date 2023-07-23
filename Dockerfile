FROM python:3.11-slim

ENV PORT=25565
ENV NAME="Minecraft Server"
ENV MOTD="Python Server Implementation"
ENV ARGS=""

RUN apt-get update -y
RUN pip install requests

COPY . /server
WORKDIR /server

CMD exec python3 main.py -p $PORT -n "$NAME" -m "$MOTD" $ARGS
