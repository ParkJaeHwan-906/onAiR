import cv2
import numpy as np
import os


# gauge config
THERMO_CFG = dict(min_angle=230, max_angle=330, min_val=0, max_val=100)
PRESS_CFG  = dict(min_angle=210, max_angle=330, min_val=0, max_val=2)



def debug_save(name, img, out_dir="debug"):
    os.makedirs(out_dir, exist_ok=True)
    cv2.imwrite(f"{out_dir}/{name}.png", img)

def visualize_angle_votes(thetas, scores, out="debug/angle_votes.png"):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(6,3))
    degs = (np.rad2deg(thetas) + 180) % 360
    plt.plot(degs, scores)
    plt.xlabel("Angle (deg)")
    plt.ylabel("Score")
    plt.tight_layout()
    plt.savefig(out)
    plt.close()

def analyze_gauge_debug(roi, cfg, out_dir="debug"):
    h, w = roi.shape[:2]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    debug_save("gray", gray, out_dir)

    blur = cv2.GaussianBlur(gray, (5,5), 0)
    debug_save("blur", blur, out_dir)

    edges = cv2.Canny(blur, 50, 150)
    debug_save("edges", edges, out_dir)

    # 중심 추정 (단순 평균 fallback)
    x0, y0 = w//2, h//2
    R = int(min(h, w) * 0.45)

    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - x0)**2 + (yy - y0)**2)
    pointer_mask = (rr > R*0.20) & (rr < R*0.60)

    edges_ptr = edges.copy()
    edges_ptr[~pointer_mask] = 0
    debug_save("pointer_masked", edges_ptr, out_dir)

    thetas = np.deg2rad(np.arange(0, 360, 1.5))
    scores = []

    for th in thetas:
        rs = np.linspace(R*0.25, R*0.9, 60)
        xs = (x0 + np.cos(th)*rs).astype(int)
        ys = (y0 - np.sin(th)*rs).astype(int)
        xs = np.clip(xs, 0, w-1)
        ys = np.clip(ys, 0, h-1)
        scores.append(edges_ptr[ys, xs].sum())

    scores = np.array(scores, float)

    visualize_angle_votes(thetas, scores, f"{out_dir}/angle_votes.png")

    best_idx = int(np.argmax(scores))
    best_angle = float((np.rad2deg(thetas[best_idx]) + 180) % 360)

    roi_vis = roi.copy()
    bx = int(x0 + np.cos(thetas[best_idx])*R)
    by = int(y0 - np.sin(thetas[best_idx])*R)
    cv2.line(roi_vis, (x0, y0), (bx, by), (0,0,255), 2)
    cv2.circle(roi_vis, (x0, y0), 4, (0,255,0), -1)
    debug_save("best_angle_overlay", roi_vis, out_dir)

    min_angle = cfg["min_angle"]
    max_angle = cfg["max_angle"]
    sweep = (min_angle - max_angle) % 360

    progressed = (best_angle - min_angle) % 360
    ratio = np.clip(progressed / sweep, 0, 1)
    value = cfg["min_val"] + ratio * (cfg["max_val"] - cfg["min_val"])

    txt = roi.copy()
    cv2.putText(txt, f"Angle: {best_angle:.2f}", (10,25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
    cv2.putText(txt, f"Value: {value:.2f}", (10,50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
    debug_save("value_display", txt, out_dir)

    return best_angle, value




if __name__ == "__main__":
    roi = cv2.imread("ther.jpeg")

    cfg = THERMO_CONFIG   # 또는 PRESS_CONFIG
    
    angle, value = analyze_gauge_debug(roi, cfg, out_dir="debug_gauge")
    
    print(angle, value)