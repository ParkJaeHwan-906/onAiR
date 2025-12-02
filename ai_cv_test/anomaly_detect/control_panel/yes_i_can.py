import cv2
import numpy as np
import os


TARGET_W = 32
TARGET_H = 64


# ------------------------------------------------------------
# normalize digit
# ------------------------------------------------------------
def normalize_digit(img):
    img = cv2.resize(img, (TARGET_W, TARGET_H), interpolation=cv2.INTER_NEAREST)
    _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    return img


# ------------------------------------------------------------
# 템플릿 로딩
# ------------------------------------------------------------
def load_templates(template_dir="template"):
    templates = {}
    for d in range(10):
        path = os.path.join(template_dir, f"{d}.png")
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[WARN] 템플릿 없음: {path}")
            continue

        templates[d] = normalize_digit(img)

    print(f"[INFO] 템플릿 {len(templates)}개 로딩 완료")
    return templates


# ------------------------------------------------------------
# 붙은 두 숫자 분리 (projection 기반)
# ------------------------------------------------------------
def split_stuck_digits(binary_img):
    h, w = binary_img.shape
    proj = np.sum(binary_img == 0, axis=0)

    thresh = max(1, int(h * 0.05))
    zeros = np.where(proj < thresh)[0]

    if len(zeros) == 0:
        return [binary_img]

    mid = w // 2
    split_col = zeros[np.argmin(np.abs(zeros - mid))]

    left = binary_img[:, :split_col]
    right = binary_img[:, split_col:]
    return [left, right]


# ------------------------------------------------------------
# digit 분리 (mask 1장 → digit 리스트)
# ------------------------------------------------------------
def extract_digits_from_mask(mask):
    # 글자=0, 배경=255로 맞춤
    _, bw = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

    # blob 찾기 (글자를 흰색으로 뒤집어서 connected components)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(255 - bw)

    digits = []

    for i in range(1, num):
        x, y, w, h, area = stats[i]
        if area < 200:
            continue

        digit = bw[y:y+h, x:x+w]

        # 붙은 숫자 판단
        if w > h * 0.75:
            parts = split_stuck_digits(digit)
            digits.extend(parts)
        else:
            digits.append(digit)

    # 정렬
    digits_sorted = sorted(digits, key=lambda img: cv2.boundingRect(255 - img)[0])
    return digits_sorted


# ------------------------------------------------------------
# XOR 기반 템플릿 매칭
# ------------------------------------------------------------
def classify_digit(digit_img, templates):
    digit_norm = normalize_digit(digit_img)

    best_digit = None
    best_score = 1e18

    for d, tmpl in templates.items():
        diff = cv2.bitwise_xor(digit_norm, tmpl)
        score = cv2.countNonZero(diff)

        if score < best_score:
            best_score = score
            best_digit = d

    return best_digit


# ------------------------------------------------------------
# digits 배열 → 최종 온도값 변환
# ------------------------------------------------------------
def digits_to_temperature(digits):
    if len(digits) == 3:
        return (digits[0] * 100 + digits[1] * 10 + digits[2]) / 10.0
    print("[WARN] digit 길이 비정상:", digits)
    return None


# ------------------------------------------------------------
# 단일 mask 이미지 OCR
# ------------------------------------------------------------
def run_single_ocr(mask_path, template_path="template"):
    templates = load_templates(template_path)

    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        print("[ERROR] 이미지 로드 실패:", mask_path)
        return

    digit_imgs = extract_digits_from_mask(mask)
    if len(digit_imgs) == 0:
        print("[ERROR] digit 분리 실패")
        return

    digits = []
    for dimg in digit_imgs:
        d = classify_digit(dimg, templates)
        digits.append(d)

    print("분류된 digits:", digits)
    final_value = digits_to_temperature(digits)
    print("최종 온도:", final_value)


# ------------------------------------------------------------
# 실행
# ------------------------------------------------------------
if __name__ == "__main__":
    # 테스트할 mask 이미지를 여기 넣기
    test_image = "masked/control_panel.jpeg"
    run_single_ocr(test_image)
