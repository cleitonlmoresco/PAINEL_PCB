import cv2
import numpy as np


def detectar_pads_com_mascara_v84(img_bgr, scale=0.6, brilho_min=110, brilho_max=245, sat_max=75, area_min=30, area_max=900, nms_dist=10, reject_vias=True, usar_gpu=False):
    """Detecta pads na placa. usar_gpu=True acelera filtros/máscaras via OpenCL (UMat).

    O resultado é idêntico ao caminho CPU (comparações inteiras equivalentes).
    """
    scale = max(0.05, min(1.0, scale)); h0, w0 = img_bgr.shape[:2]
    img_work = cv2.resize(img_bgr, (max(1, int(w0*scale)), max(1, int(h0*scale))), interpolation=cv2.INTER_AREA) if scale != 1.0 else img_bgr.copy()
    kc = max(3, int(25*scale/0.6)); ke = max(3, int(20*scale/0.6))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kc, kc))
    k_er = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ke, ke))
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))

    mask_pad = mask_green = None; S = V = None; usou_gpu = False
    if usar_gpu:
        try:
            if not (cv2.ocl.haveOpenCL() and cv2.ocl.useOpenCL()):
                raise RuntimeError("OpenCL desligado")
            u_work = cv2.UMat(img_work)
            u_blur = cv2.bilateralFilter(u_work, 5, 40, 40)
            u_hsv = cv2.cvtColor(u_blur, cv2.COLOR_BGR2HSV)
            S_u, V_u = cv2.split(u_hsv)
            # equivalentes inteiros exatos das comparações numpy do caminho CPU
            m_s = cv2.threshold(S_u, sat_max-1, 255, cv2.THRESH_BINARY_INV)[1]      # S < sat_max
            m_v1 = cv2.threshold(V_u, brilho_min, 255, cv2.THRESH_BINARY)[1]        # V > brilho_min
            m_v2 = cv2.threshold(V_u, brilho_max-1, 255, cv2.THRESH_BINARY_INV)[1]  # V < brilho_max
            mask_pad_u = cv2.bitwise_and(cv2.bitwise_and(m_s, m_v1), m_v2)
            mask_green_u = cv2.inRange(u_hsv, np.array([35, 25, 25]), np.array([85, 255, 255]))
            mask_green_u = cv2.morphologyEx(mask_green_u, cv2.MORPH_CLOSE, k_close, iterations=4)
            mask_green = mask_green_u.get()
            hsv_np = u_hsv.get(); S = hsv_np[:, :, 1]; V = hsv_np[:, :, 2]
            cnts, _ = cv2.findContours(mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            roi = np.zeros(mask_green.shape, dtype=np.uint8)
            if cnts:
                maior = max(cnts, key=cv2.contourArea); cv2.drawContours(roi, [maior], -1, 255, -1)
            else:
                roi[:] = 255
            roi_u = cv2.erode(cv2.UMat(roi), k_er, iterations=1)
            mask_pad_u = cv2.bitwise_and(mask_pad_u, roi_u)
            mask_pad_u = cv2.morphologyEx(mask_pad_u, cv2.MORPH_OPEN, k1, iterations=1)
            mask_pad_u = cv2.morphologyEx(mask_pad_u, cv2.MORPH_CLOSE, k1, iterations=1)
            mask_pad = mask_pad_u.get()
            usou_gpu = True
        except Exception:
            usou_gpu = False

    if not usou_gpu:
        img_work_blur = cv2.bilateralFilter(img_work, 5, 40, 40); hsv = cv2.cvtColor(img_work_blur, cv2.COLOR_BGR2HSV); H, S, V = cv2.split(hsv)
        mask_pad = ((S < sat_max) & (V > brilho_min) & (V < brilho_max)).astype(np.uint8)*255
        mask_green = cv2.inRange(hsv, np.array([35, 25, 25]), np.array([85, 255, 255]))
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, k_close, iterations=4)
        cnts, _ = cv2.findContours(mask_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi = np.zeros(mask_pad.shape, dtype=np.uint8)
        if cnts:
            maior = max(cnts, key=cv2.contourArea); cv2.drawContours(roi, [maior], -1, 255, -1)
        else:
            roi[:] = 255
        roi = cv2.erode(roi, k_er, iterations=1); mask_pad = cv2.bitwise_and(mask_pad, roi)
        mask_pad = cv2.morphologyEx(mask_pad, cv2.MORPH_OPEN, k1, iterations=1)
        mask_pad = cv2.morphologyEx(mask_pad, cv2.MORPH_CLOSE, k1, iterations=1)

    cnts, _ = cv2.findContours(mask_pad, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pads = []
    for cnt in cnts:
        area = cv2.contourArea(cnt); area_orig = area/(scale*scale)
        if area_orig < area_min or area_orig > area_max: continue
        perim = cv2.arcLength(cnt, True)
        if perim == 0: continue
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 3 or h < 3: continue
        hull = cv2.convexHull(cnt); hull_a = cv2.contourArea(hull); sol = area/hull_a if hull_a > 0 else 0; extent = area/(w*h) if w*h > 0 else 0; aspect = max(w, h)/max(1, min(w, h))
        if extent < 0.4 or sol < 0.6 or aspect > 4.0: continue
        M = cv2.moments(cnt)
        if M["m00"] == 0: continue
        cx_w = int(M["m10"]/M["m00"]); cy_w = int(M["m01"]/M["m00"])
        if reject_vias:
            x1 = max(0, cx_w-2); x2 = min(V.shape[1], cx_w+3); y1 = max(0, cy_w-2); y2 = min(V.shape[0], cy_w+3)
            roi_v = V[y1:y2, x1:x2]
            if roi_v.size > 0:
                mean_v = np.mean(roi_v); roi_s = S[y1:y2, x1:x2]; mean_s = np.mean(roi_s) if roi_s.size > 0 else 0
                if mean_v < 75 and mean_s < 90: continue
                if w > 0 and h > 0:
                    circularity = 4*np.pi*area/(perim*perim) if perim > 0 else 0
                    if circularity > 0.65 and mean_v < 95: continue
        cx = int(cx_w/scale); cy = int(cy_w/scale)
        pads.append({"cx": cx, "cy": cy, "w": int(w/scale), "h": int(h/scale), "area": int(area_orig), "manual": False})
    pads.sort(key=lambda p: p["area"], reverse=True); keep = []
    for p in pads:
        if any(np.hypot(p["cx"]-q["cx"], p["cy"]-q["cy"]) < nms_dist*2 for q in keep): continue
        keep.append(p)
    keep.sort(key=lambda p: (p["cy"]//80, p["cx"]))
    mask_full = cv2.resize(mask_pad, (w0, h0), interpolation=cv2.INTER_NEAREST)
    return keep, mask_full


def detectar_pads_tiles(img_bgr, tile=1800, overlap=220, usar_gpu=False, **params):
    """Detecção por tiles (placas grandes): roda o detector em blocos e funde com NMS."""
    h, w = img_bgr.shape[:2]
    nms = max(4, int(params.get('nms_dist', 10)))
    todos = []
    passo = max(200, int(tile) - int(overlap))
    y = 0
    while True:
        y2 = min(h, y + int(tile))
        x = 0
        while True:
            x2 = min(w, x + int(tile))
            sub = img_bgr[y:y2, x:x2]
            if min(sub.shape[:2]) >= 80:
                pads, _ = detectar_pads_com_mascara_v84(sub, scale=1.0, usar_gpu=usar_gpu, **params)
                for p in pads:
                    q = dict(p); q['cx'] += x; q['cy'] += y
                    todos.append(q)
            if x2 >= w:
                break
            x += passo
        if y2 >= h:
            break
        y += passo
    todos.sort(key=lambda p: p['area'], reverse=True)
    keep = []
    for p in todos:
        if any(np.hypot(p['cx'] - q['cx'], p['cy'] - q['cy']) < nms for q in keep):
            continue
        keep.append(p)
    keep.sort(key=lambda p: (p['cy'] // 80, p['cx']))
    return keep
