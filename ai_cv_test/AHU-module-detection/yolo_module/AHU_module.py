from roboflow import Roboflow
rf = Roboflow(api_key="DinqGliDFENS7p4I8UlS")
project = rf.workspace("boiler-chiller").project("ahu-module-detection-fnnpj")
version = project.version(2)
dataset = version.download("yolov11")
                