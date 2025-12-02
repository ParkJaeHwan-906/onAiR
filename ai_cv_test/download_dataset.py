from roboflow import Roboflow


rf = Roboflow(api_key="DinqGliDFENS7p4I8UlS")
project = rf.workspace("boiler-chiller").project("onair-g8fkz")
version = project.version(1)
dataset = version.download("yolov11")
                