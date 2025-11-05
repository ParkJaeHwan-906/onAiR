import cv2

def load_image(idx):
    path = f"../data/{idx}.jpg"
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError("Not Found.")
    return img