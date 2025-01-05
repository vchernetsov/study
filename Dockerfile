FROM tensorflow/tensorflow:2.13.0-gpu-jupyter


RUN pip install --no-cache-dir \
    pydot \
    graphviz

RUN apt-get update
RUN apt-get -y install htop nvtop