from roboflow import Roboflow
rf = Roboflow(api_key="DinqGliDFENS7p4I8UlS")
project = rf.workspace("boiler-chiller").project("object-detection-ueasf")
version = project.version(3)
dataset = version.download("yolov11")
                