FROM tensorflow/tensorflow:2.13.0-gpu-jupyter

RUN python3 -m pip install --upgrade pip

RUN apt-get update
RUN apt-get -y install htop nvtop
RUN apt-get -y install python3-graphviz graphviz python3-pydot python3-pydot-ng
