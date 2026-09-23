# Don't Remove Credit @Fair033838 
# Subscribe YouTube Channel For Amazing Bot @newnatokmoviehere 
# Ask Doubt on telegram @ss_anime_box 

FROM python:3.10.8-slim-buster

RUN apt update && apt upgrade -y
RUN apt install git -y
COPY requirements.txt /requirements.txt

RUN cd /
RUN pip3 install -U pip && pip3 install -U -r requirements.txt
RUN mkdir /VJ-Video-Player
WORKDIR /VJ-Video-Player
COPY . /VJ-Video-Player
CMD ["python", "bot.py"]
