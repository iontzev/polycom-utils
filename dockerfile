FROM python:3.7.4-slim-buster

# create workdir
WORKDIR /code

# install python modules
COPY requirements.txt cam.py ./
RUN pip3 install --no-cache-dir -r requirements.txt

# run python after start docker container
CMD [ "python3", "./cam.py" ]
