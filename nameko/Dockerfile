FROM centos:7

RUN yum update -y ; \
    yum install -y epel-release ; \
    yum install -y gcc make python-devel python kernel-devel python2-pip
RUN pip install --upgrade pip ; \
    pip install virtualenv nameko

RUN virtualenv -p python /appenv
RUN . /appenv/bin/activate

RUN mkdir /var/nameko

WORKDIR /var/nameko
