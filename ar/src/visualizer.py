import cv2

def draw_keypoints(img, keypoints):
    """이미지 위에 특징점 표시 (점으로 변경)"""
    # flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS 를 제거하거나 cv2.DRAW_MATCHES_FLAGS_DEFAULT 등으로 변경
    img_kp = cv2.drawKeypoints(
        img, keypoints, None, color=(0, 255, 0)
        # flags=cv2.DRAW_MATCHES_FLAGS_DEFAULT # 기본값은 작은 원으로 표시하지만, 풍부한 정보를 담지 않음
    )
    return img_kp

def show_image(win_name, img, scale=0.3):
    """이미지 시각화"""
    h, w = img.shape[:2]
    resized = cv2.resize(img, (int(w * scale), int(h * scale)))
    cv2.imshow(win_name, resized)
    cv2.waitKey(0)
    cv2.destroyAllWindows()