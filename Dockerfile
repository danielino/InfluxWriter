FROM namekopy2:latest

COPY requirements.txt /var/nameko/

RUN pip install -r requirements.txt

COPY . /var/nameko/

COPY conf /var/nameko/conf

CMD ["nameko", "run", "service", "--config", "conf/nameko.yml"]
