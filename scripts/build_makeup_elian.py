import os
import sys
import json
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if racine not in sys.path:
    sys.path.insert(0, racine)

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PORTRAIT = os.path.join(r"C:\test", "L'HERITIER DU VIDE", "assets", "portraits", "elian_portrait.png")
MODELE_YUNET = r"C:\Modeles_LLM\onnx\face_detection_yunet_2023mar.onnx"
SKIN_ELIAN = os.path.join(racine, "godot_assets", "skins", "elian_enfant", "elian_enfant_diffuse.png")

DIR_INK_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\ink_layers"
DIR_INK_DEPOT = os.path.join(racine, "godot_assets", "skins", "elian_enfant", "makeup")
DIR_EYES_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\eyes\materials"
NOM_INK = "elian_fatigue_ventgris"

# MakeHuman hm08 UV face symmetry
Y_SYM = 1058

def detecter_reperes(img_bgr):
    h, w = img_bgr.shape[:2]
    det = cv2.FaceDetectorYN.create(MODELE_YUNET, "", (w, h), score_threshold=0.6)
    _, faces = det.detect(img_bgr)
    if faces is None or len(faces) == 0:
        raise RuntimeError("YuNet: no face detected in the portrait")
    f = faces[0]
    return {
        "re": (float(f[4]), float(f[5])),
        "le": (float(f[6]), float(f[7])),
        "nose": (float(f[8]), float(f[9])),
        "rmouth": (float(f[10]), float(f[11])),
        "lmouth": (float(f[12]), float(f[13])),
        "score": float(f[14]),
        "bbox": (float(f[0]), float(f[1]), float(f[2]), float(f[3]))
    }

def echantillonner(arr, cx, cy, rx, ry):
    h, w = arr.shape[:2]
    x0, x1 = max(0, int(cx - rx)), min(w, int(cx + rx))
    y0, y1 = max(0, int(cy - ry)), min(h, int(cy + ry))
    roi = arr[y0:y1, x0:x1].astype(np.float32)
    lab = cv2.cvtColor(arr[y0:y1, x0:x1], cv2.COLOR_BGR2Lab).astype(np.float32)
    return roi.mean(axis=(0, 1)), lab.mean(axis=(0, 1))

def draw_feathered(shapes, blur_radius):
    coul = Image.new("RGB", (2048, 2048), (0, 0, 0))
    alpha = Image.new("L", (2048, 2048), 0)
    dc = ImageDraw.Draw(coul)
    da = ImageDraw.Draw(alpha)
    for item in shapes:
        stype = item[0]
        if stype == "ellipse":
            _, coords, rgb, a = item
            r, g, b = int(rgb[2]), int(rgb[1]), int(rgb[0])
            a_int = int(a * 255)
            dc.ellipse(coords, fill=(r, g, b))
            da.ellipse(coords, fill=a_int)
        elif stype == "line":
            _, xy, width, rgb, a = item
            r, g, b = int(rgb[2]), int(rgb[1]), int(rgb[0])
            a_int = int(a * 255)
            dc.line(xy, fill=(r, g, b), width=width)
            da.line(xy, fill=a_int, width=width)
        elif stype == "polygon":
            _, pts, rgb, a = item
            r, g, b = int(rgb[2]), int(rgb[1]), int(rgb[0])
            a_int = int(a * 255)
            dc.polygon(pts, fill=(r, g, b))
            da.polygon(pts, fill=a_int)
    if blur_radius > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        coul = coul.filter(ImageFilter.GaussianBlur(radius=max(1, blur_radius // 2)))
    res = Image.new("RGBA", (2048, 2048), (0, 0, 0, 0))
    res.paste(coul, (0, 0))
    res.putalpha(alpha)
    return res

def main():
    print("=" * 70)
    print(" 💄 ELIAN MAKEUP & EYES: PORTRAIT EXTRACTION -> MPFB MAKEUP INK LAYER ")
    print("=" * 70)

    # 1. Portrait analysis
    portrait = cv2.imread(PORTRAIT)
    if portrait is None:
        raise FileNotFoundError(f"Portrait not found: {PORTRAIT}")
    rep = detecter_reperes(portrait)
    re, le = rep["re"], rep["le"]
    ipd = np.hypot(le[0] - re[0], le[1] - re[1])
    print(f"  🔍 YuNet score={rep['score']:.2f} | IPD={ipd:.1f}px")

    # Sampling
    joue_vl, l_jvl = echantillonner(portrait, re[0] - 0.25*ipd, re[1] + 0.65*ipd, 0.15*ipd, 0.15*ipd)
    joue_vr, l_jvr = echantillonner(portrait, le[0] + 0.25*ipd, le[1] + 0.65*ipd, 0.15*ipd, 0.15*ipd)
    joue_p = (joue_vl + joue_vr) / 2.0
    l_joue = (l_jvl[0] + l_jvr[0]) / 2.0

    cerne_vl, l_cvl = echantillonner(portrait, re[0], re[1] + 0.22*ipd, 0.18*ipd, 0.09*ipd)
    cerne_vr, l_cvr = echantillonner(portrait, le[0], le[1] + 0.22*ipd, 0.18*ipd, 0.09*ipd)
    cerne_p = (cerne_vl + cerne_vr) / 2.0
    l_cerne = (l_cvl[0] + l_cvr[0]) / 2.0

    temple_vl, _ = echantillonner(portrait, re[0] - 0.55*ipd, re[1] - 0.05*ipd, 0.12*ipd, 0.15*ipd)
    temple_vr, _ = echantillonner(portrait, le[0] + 0.55*ipd, le[1] - 0.05*ipd, 0.12*ipd, 0.15*ipd)
    temple_p = (temple_vl + temple_vr) / 2.0

    lips_p, _ = echantillonner(portrait, (rep["rmouth"][0]+rep["lmouth"][0])/2,
                               (rep["rmouth"][1]+rep["lmouth"][1])/2, 0.16*ipd, 0.07*ipd)

    delta_cerne = l_joue - l_cerne
    ratio_cerne = cerne_p / np.maximum(joue_p, 1.0)
    ratio_temple = temple_p / np.maximum(joue_p, 1.0)
    ratio_lips = lips_p / np.maximum(joue_p, 1.0)

    print(f"  🎨 Portrait measurements: ΔL dark circles={delta_cerne:.1f}")
    print(f"     Dark circle/Cheek ratio (BGR): {ratio_cerne.round(3)}")
    print(f"     Temple/Cheek ratio (BGR): {ratio_temple.round(3)}")

    # 2. Transfer to the Grey-Wind 3D gamut
    skin = cv2.imread(SKIN_ELIAN)
    joue_3d = skin[910:970, 1840:1900].astype(np.float32).mean(axis=(0, 1)) # BGR

    # Dark circles: cold hollow shadow, darkened to compensate SSS diffusion
    c_arr = np.clip(joue_3d * ratio_cerne * 0.82, 0, 255)
    cernes_bgr = tuple(float(x) for x in c_arr)
    # Dark-circle core: subtle purple/anthracite shade
    cernes_core_bgr = tuple(float(x) for x in np.clip(c_arr * np.array([1.02, 0.92, 1.02]), 0, 255))
    # Hollow temples
    temple_bgr = tuple(float(x) for x in np.clip(joue_3d * ratio_temple * 0.88, 0, 255))
    # Fatigue flush on cheeks
    blush_bgr = tuple(float(x) for x in np.clip(joue_3d * np.array([0.88, 0.90, 1.08]), 0, 255))
    # Upper eyelid hollow
    crease_bgr = tuple(float(x) for x in np.clip(c_arr * 0.92, 0, 255))
    # Natural lip tint
    lips_bgr = tuple(float(x) for x in np.clip(joue_3d * ratio_lips * 1.05, 0, 255))

    print("  🖌️ 3D target colors (RGB):")
    print(f"     Dark circles  : {tuple(int(x) for x in cernes_bgr[::-1])}")
    print(f"     Circle core   : {tuple(int(x) for x in cernes_core_bgr[::-1])}")
    print(f"     Temples       : {tuple(int(x) for x in temple_bgr[::-1])}")
    print(f"     Lips          : {tuple(int(x) for x in lips_bgr[::-1])}")

    # 3. Anatomical painting of the layers
    pts_mid_L = [(1728, 1012), (1742, 1002), (1752, 985), (1748, 965), (1736, 950)]
    pts_mid_R = [(1728, 1104), (1742, 1114), (1752, 1131), (1748, 1151), (1736, 1166)]

    # Layer 1: diffuse penumbra (orbit, temples, cheeks, nose)
    wide_shapes = []
    for pts in [pts_mid_L, pts_mid_R]:
        for (x, y) in pts:
            wide_shapes.append(("ellipse", [x - 26, y - 25, x + 26, y + 25], cernes_bgr, 0.52))
    # Hollow temples
    wide_shapes.append(("ellipse", [1680 - 45, 860 - 35, 1680 + 45, 860 + 35], temple_bgr, 0.48))
    wide_shapes.append(("ellipse", [1680 - 45, 1256 - 35, 1680 + 45, 1256 + 35], temple_bgr, 0.48))
    # Cheekbone fatigue blush
    wide_shapes.append(("ellipse", [1865 - 35, 940 - 28, 1865 + 35, 940 + 28], blush_bgr, 0.32))
    wide_shapes.append(("ellipse", [1865 - 35, 1176 - 28, 1865 + 35, 1176 + 28], blush_bgr, 0.32))
    # Nose bridge
    wide_shapes.append(("ellipse", [1745 - 20, 1058 - 14, 1745 + 20, 1058 + 14], temple_bgr, 0.28))
    layer_wide = draw_feathered(wide_shapes, blur_radius=14)

    # Layer 2: intermediate orbital crescent (covers from the palpebral edge to the hollow)
    med_shapes = []
    for pts in [pts_mid_L, pts_mid_R]:
        for i in range(len(pts) - 1):
            med_shapes.append(("line", [pts[i], pts[i+1]], 30, cernes_bgr, 0.68))
        for (x, y) in pts:
            med_shapes.append(("ellipse", [x - 17, y - 18, x + 17, y + 18], cernes_bgr, 0.70))
    layer_med = draw_feathered(med_shapes, blur_radius=8)

    # Layer 3: deep fatigue furrow (tear trough & orbital center)
    core_shapes = []
    for pts in [pts_mid_L[:3], pts_mid_R[:3]]:
        for i in range(len(pts) - 1):
            core_shapes.append(("line", [pts[i], pts[i+1]], 16, cernes_core_bgr, 0.82))
    core_shapes.append(("ellipse", [1746 - 12, 988 - 16, 1746 + 12, 988 + 16], cernes_core_bgr, 0.85))
    core_shapes.append(("ellipse", [1746 - 12, 1128 - 16, 1746 + 12, 1128 + 16], cernes_core_bgr, 0.85))
    layer_core = draw_feathered(core_shapes, blur_radius=5)

    # Layer 4: upper palpebral hollow (shadow under the arch)
    crease_shapes = []
    pts_crease_L = [(1705, 1005), (1702, 985), (1708, 965)]
    pts_crease_R = [(1705, 1111), (1702, 1131), (1708, 1151)]
    for i in range(2):
        crease_shapes.append(("line", [pts_crease_L[i], pts_crease_L[i+1]], 12, crease_bgr, 0.50))
        crease_shapes.append(("line", [pts_crease_R[i], pts_crease_R[i+1]], 12, crease_bgr, 0.50))
    layer_crease = draw_feathered(crease_shapes, blur_radius=5)

    # Layer 5: soft lip tint
    lip_shapes = [
        ("ellipse", [1938 - 12, 1058 - 36, 1938 + 12, 1058 + 36], lips_bgr, 0.40)
    ]
    layer_lips = draw_feathered(lip_shapes, blur_radius=6)

    # Final composition of the RGBA ink layer
    final_ink = Image.new("RGBA", (2048, 2048), (0, 0, 0, 0))
    final_ink = Image.alpha_composite(final_ink, layer_wide)
    final_ink = Image.alpha_composite(final_ink, layer_med)
    final_ink = Image.alpha_composite(final_ink, layer_core)
    final_ink = Image.alpha_composite(final_ink, layer_crease)
    final_ink = Image.alpha_composite(final_ink, layer_lips)

    # Official MPFB manifest
    manifest = {
        "name": "Elian fatigue Vent-Gris",
        "focus": "",
        "image_name": NOM_INK + ".png",
        "extraction": {
            "source": PORTRAIT,
            "yunet_score": round(rep["score"], 3),
            "delta_lumiere_cernes": round(float(delta_cerne), 1),
            "ratio_cerne_bgr": [round(float(x), 3) for x in ratio_cerne],
            "couleurs_bgr": {
                "cernes": [round(float(x), 1) for x in cernes_bgr],
                "cernes_core": [round(float(x), 1) for x in cernes_core_bgr],
                "temples": [round(float(x), 1) for x in temple_bgr],
                "blush": [round(float(x), 1) for x in blush_bgr],
                "lips": [round(float(x), 1) for x in lips_bgr],
            },
            "calques": ["wide_penumbra", "med_crescent", "core_tear_trough", "eyelid_crease", "lips_soft"],
        },
    }

    # Saves
    for d in [DIR_INK_MPFB, DIR_INK_DEPOT]:
        os.makedirs(d, exist_ok=True)
        final_ink.save(os.path.join(d, NOM_INK + ".png"), "PNG")
        with open(os.path.join(d, NOM_INK + ".json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("  ✅ Ink layer PNG:", os.path.join(DIR_INK_MPFB, NOM_INK + ".png"))
    print("  ✅ Manifest JSON:", os.path.join(DIR_INK_MPFB, NOM_INK + ".json"))

    # 4. Generating Elian's cyan eye texture
    src_eye = os.path.join(DIR_EYES_MPFB, "lightblue_eye.png")
    dst_eye_mpfb = os.path.join(DIR_EYES_MPFB, "elian_cyan_eye.png")
    dst_eye_depot = os.path.join(racine, "godot_assets", "skins", "elian_enfant", "elian_cyan_eye.png")

    eye_img = cv2.imread(src_eye, cv2.IMREAD_UNCHANGED)
    if eye_img is not None:
        eye_hsv = cv2.cvtColor(eye_img[:,:,:3], cv2.COLOR_BGR2HSV).astype(np.float32)
        blue_mask = (eye_hsv[:,:,1] > 40) & (eye_hsv[:,:,0] >= 90) & (eye_hsv[:,:,0] <= 135)
        eye_hsv[blue_mask, 0] = np.clip(eye_hsv[blue_mask, 0] - 16.0, 78, 105) # toward cyan/turquoise
        eye_hsv[blue_mask, 2] = np.clip(eye_hsv[blue_mask, 2] * 1.15, 0, 255) # inner glow
        eye_hsv[blue_mask, 1] = np.clip(eye_hsv[blue_mask, 1] * 1.05, 0, 255)
        cyan_bgr = cv2.cvtColor(eye_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        if eye_img.shape[2] == 4:
            cyan_out = np.dstack([cyan_bgr, eye_img[:,:,3]])
        else:
            cyan_out = cyan_bgr
        cv2.imwrite(dst_eye_mpfb, cyan_out)
        cv2.imwrite(dst_eye_depot, cyan_out)
        print("  ✅ Elian cyan eyes:", dst_eye_mpfb)

    print("\n" + "=" * 70)
    print(" 🎉 ELIAN MAKEUP & EYES GENERATED SUCCESSFULLY ")
    print("=" * 70)

if __name__ == "__main__":
    main()
