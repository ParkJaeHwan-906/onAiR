import cv2
import numpy as np

def track_features(prev_gray, cur_gray, prev_pts, fb_thresh=1.0):
    if prev_pts is None or len(prev_pts) == 0:
        return np.array([]), np.array([]), np.array([])

    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    )

    # Forward
    next_pts, status_fwd, err_fwd = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, prev_pts, None, **lk_params)
    if next_pts is None:
        return np.array([]), np.array([]), np.array([])

    # Backward
    back_pts, status_bwd, _ = cv2.calcOpticalFlowPyrLK(cur_gray, prev_gray, next_pts, None, **lk_params)

    # FB error
    fb_err = np.linalg.norm(prev_pts - back_pts, axis=2)

    valid = (status_fwd.flatten() == 1) & (status_bwd.flatten() == 1)
    valid &= (fb_err.flatten() < fb_thresh)

    err_good = err_fwd[valid]
    if len(err_good) > 0:
        med_err = np.median(err_good)
        valid[valid] &= (err_fwd[valid].flatten() < 2.5 * med_err)

    # NaN 제거 수정된 부분 👇
    next_pts_valid = next_pts[valid]
    prev_pts_valid = prev_pts[valid]
    not_nan = ~np.isnan(next_pts_valid).any(axis=(1, 2))
    next_pts_valid = next_pts_valid[not_nan]
    prev_pts_valid = prev_pts_valid[not_nan]

    if len(prev_pts_valid) < 5:
        return np.array([]), np.array([]), np.array([])

    return (
        prev_pts_valid.reshape(-1, 1, 2).astype(np.float32),
        next_pts_valid.reshape(-1, 1, 2).astype(np.float32),
        valid.astype(np.uint8)
    )
