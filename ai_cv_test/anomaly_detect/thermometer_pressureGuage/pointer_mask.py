import cv2
import numpy as np
import os

def pointer_mask_debug(roi, edges, out_dir="debug_step03"):
    os.makedirs(out_dir, exist_ok=True)

    h, w = edges.shape[:2]

    x0, y0 = w // 2, h // 2
    R = int(min(h, w) * 0.45)

    yy, xx = np.indices(edges.shape)
    rr = np.sqrt((xx - x0)**2 + (yy - y0)**2)

    mask = (rr > R*0.15) & (rr < R*0.90)

    masked_edges = edges.copy()
    masked_edges[~mask] = 0

    cv2.imwrite(f"{out_dir}/04_pointer_mask_only.png", (mask*255).astype(np.uint8))
    cv2.imwrite(f"{out_dir}/05_edges_after_mask.png", masked_edges)

    return masked_edges


if __name__ == "__main__":
    roi = cv2.imread("roi_debug/roi_167_42.png")
    edges = cv2.imread("debug_step02/03_edges.png", 0)
    masked_edges = pointer_mask_debug(roi, edges)