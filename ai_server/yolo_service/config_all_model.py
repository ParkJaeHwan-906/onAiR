
ALL_MODEL_PATH = "/app/ai_server/yolo_service/models/best.pt"

ALL_CLASS_NAMES = [
    "AHU", "AHU_pannel", "Boiler", "Chiler", "belt",
    "button_off", "button_on", "control_panel", "overheat_light",
    "power_light", "pressure_gauge", "run_light",
    "temperature_FND", "thermometer"
]

DEVICE_CLASSES = {"AHU", "Boiler", "Chiler"}

MODULE_CLASSES = {
    "belt",
    "control_panel",
    "pressure_gauge",
    "thermometer",
    "AHU_pannel",
}

PANEL_parts = {
    "run_light",
    "power_light",
    "overheat_light",
    "button_on",
    "button_off",
    "temperature_FND",
}

