import os
import cv2
import numpy as np
from ultralytics import YOLO

# -----------------------
# 경로 설정
# -----------------------
PANEL_MODEL_PATH = "../../control-panel-5/runs/train/panel_yolo11n2/weights/best.pt"
IMAGE_DIR = "origin"                    # 원본 사진 폴더
TEMPLATE_SAVE_DIR = "digit_templates"   # 최종 평균 템플릿 저장 폴더
CANDIDATE_DIR = "digit_candidates"      # 개별 숫자 후보 저장 폴더
DEBUG_ROI_DIR = "debug_roi"             # temperature ROI 저장
DEBUG_MASK_DIR = "debug_mask"           # mask 저장

os.makedirs(TEMPLATE_SAVE_DIR, exist_ok=True)
os.makedirs(CANDIDATE_DIR, exist_ok=True)
os.makedirs(DEBUG_ROI_DIR, exist_ok=True)
os.makedirs(DEBUG_MASK_DIR, exist_ok=True)

digit_collect = {i: [] for i in range(10)}


# -----------------------
# 1) temperature ROI 찾기
# -----------------------
def get_temperature_roi(img, panel_model, basename):
    results = panel_model.predict(img, conf=0.5, device="cpu", verbose=False)
    temp_roi = None

    for box in results[0].boxes:
        cls_name = results[0].names[int(box.cls)]
        if cls_name == "temperature":
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            temp_roi = img[y1:y2, x1:x2]
            break

    if temp_roi is not None:
        cv2.imwrite(os.path.join(DEBUG_ROI_DIR, f"{basename}_temp_roi.jpg"), temp_roi)

    return temp_roi


# -----------------------
# 2) ROI 안에서 빨간 세그먼트 마스크 생성 (HSV + R 채널)
# -----------------------
def make_red_mask(temp_roi, basename):
    h, w = temp_roi.shape[:2]

    # ① HSV 기반 빨간색
    hsv = cv2.cvtColor(temp_roi, cv2.COLOR_BGR2HSV)

    # 이전보다 S,V 하한을 낮춰서 더 많이 잡음
    mask1 = cv2.inRange(hsv, (0, 40, 40), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (170, 40, 40), (180, 255, 255))
    hsv_mask = cv2.bitwise_or(mask1, mask2)

    # ② R 채널 기반: R이 G,B보다 충분히 크고, 절대값도 일정 이상
    b, g, r = cv2.split(temp_roi)
    r = r.astype(np.int16)
    g = g.astype(np.int16)
    b = b.astype(np.int16)

    dominance = (r - np.maximum(g, b)) > 30       # R이 다른 채널보다 30 이상 큼
    strong = r > 120                               # R 자체도 밝음
    rb_mask = (dominance & strong).astype(np.uint8) * 255

    # ③ 둘 다 합치기
    mask = cv2.bitwise_or(hsv_mask, rb_mask)

    # ④ morphology 로 정리
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # 디버그 저장
    cv2.imwrite(os.path.join(DEBUG_MASK_DIR, f"{basename}_mask.jpg"), mask)

    return mask


# -----------------------
# 3) 마스크에서 각 숫자 컨투어 추출
# -----------------------
def extract_digit_boxes(mask):
    h, w = mask.shape[:2]

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )

    boxes = []

    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]

        if area < 30:
            continue  # 너무 작은 노이즈

        aspect = bh / (bw + 1e-6)

        # 세로로 너무 납작하면 세그먼트 하나일 확률 높음
        if aspect < 0.8:
            continue

        # 한 자리 숫자가 아닌, 전체 숫자 뭉텅이로 묶인 박스 거르기
        if bw > w * 0.6 and area > 200:
            continue

        boxes.append((x, y, bw, bh))

    # 좌우 정렬
    boxes = sorted(boxes, key=lambda b: b[0])
    return boxes


# -----------------------
# 4) 각 숫자 crop → 정규화 → 파일 저장 + 라벨링
# -----------------------
def collect_templates_from_image(img_path, panel_model):
    global digit_collect

    basename = os.path.splitext(os.path.basename(img_path))[0]
    print(f"\n[INFO] 이미지 처리: {img_path}")

    img = cv2.imread(img_path)
    if img is None:
        print("  로드 실패")
        return

    temp_roi = get_temperature_roi(img, panel_model, basename)
    if temp_roi is None:
        print("  temperature 박스 탐지 실패")
        return

    mask = make_red_mask(temp_roi, basename)
    digit_boxes = extract_digit_boxes(mask)

    if not digit_boxes:
        nz = int((mask > 0).sum())
        print(f"  숫자 컨투어 없음 (mask non-zero: {nz})")
        return

    for idx, (x, y, bw, bh) in enumerate(digit_boxes):
        pad = 2
        x0 = max(x - pad, 0)
        y0 = max(y - pad, 0)
        x1 = min(x + bw + pad, mask.shape[1])
        y1 = min(y + bh + pad, mask.shape[0])

        digit = mask[y0:y1, x0:x1]

        # 정규화 크기
        digit = cv2.resize(digit, (28, 48), interpolation=cv2.INTER_AREA)
        digit_norm = digit.astype(np.float32) / 255.0

        cand_path = os.path.join(CANDIDATE_DIR, f"{basename}_d{idx}.png")
        cv2.imwrite(cand_path, (digit_norm * 255).astype(np.uint8))

        print(f"  후보 저장: {cand_path}")
        lbl = input("    이 숫자는 무엇입니까? (0~9, 엔터=스킵) → ").strip()

        if lbl.isdigit() and len(lbl) == 1:
            d = int(lbl)
            digit_collect[d].append(digit_norm)
        else:
            print("    스킵")


# -----------------------
# 5) 숫자별 평균 템플릿 저장
# -----------------------
def save_final_templates():
    print("\n[INFO] 최종 템플릿 저장 시작")
    for num, imgs in digit_collect.items():
        if len(imgs) == 0:
            print(f"  숫자 {num}: 수집된 샘플 없음, 건너뜀")
            continue
        arr = np.mean(imgs, axis=0)
        arr_u8 = (arr * 255).astype(np.uint8)
        out_path = os.path.join(TEMPLATE_SAVE_DIR, f"{num}.png")
        cv2.imwrite(out_path, arr_u8)
        print(f"  숫자 {num}: {len(imgs)}개 평균 → {out_path}")
    print("[INFO] 템플릿 저장 완료")


def main():
    panel_model = YOLO(PANEL_MODEL_PATH)

    files = sorted(os.listdir(IMAGE_DIR))
    for f in files:
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            img_path = os.path.join(IMAGE_DIR, f)
            collect_templates_from_image(img_path, panel_model)

    save_final_templates()


if __name__ == "__main__":
    main()
