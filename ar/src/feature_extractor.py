import cv2
import numpy as np

class FeatureExtractor:
    def __init__(self, nfeatures: int = 1000):
        # ORB 특징점 추출기 초기화
        self.orb = cv2.ORB_create(nfeatures=nfeatures)

    def extract(self, img):
        keypoints, descriptors = self.orb.detectAndCompute(img, None)
        print(f"Detected keypoints : {len(keypoints)}")
        return keypoints, descriptors