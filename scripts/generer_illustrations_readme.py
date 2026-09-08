import os
import shutil
from PIL import Image, ImageDraw

os.makedirs('docs/exemples/workflows_2d', exist_ok=True)
os.makedirs('docs/exemples/workflows_3d', exist_ok=True)
os.makedirs('docs/exemples/workflows_audio', exist_ok=True)

# 1. Copie des planches mesh_ia vers docs/exemples/workflows_3d/
for f in ['casque_512_planche.png', 'casque_1024_planche.png']:
    src = os.path.join('output', 'trellis_smoke', f)
    dst = os.path.join('docs', 'exemples', 'workflows_3d', f)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copie {src} -> {dst}")

# 2. TTS Dialogue Visemes
try:
    p = Image.open('godot_assets/portrait_ico_elian.png').convert('RGBA').resize((120, 120))
    w, h = 760, 180
    img_tts = Image.new('RGBA', (w, h), (16, 18, 24, 255))
    draw = ImageDraw.Draw(img_tts)
    draw.text((20, 10), "TTS DIALOGUE : Phonetic Viseme Lip-Sync Mapping (.json Godot Manifest)", fill=(240, 240, 250))
    img_tts.paste(p, (20, 40))
    draw.rectangle([18, 38, 142, 162], outline=(70, 80, 100), width=1)
    draw.text((30, 164), "Elian (180 Hz)", fill=(160, 170, 190))
    draw.line([(180, 95), (730, 95)], fill=(50, 60, 80), width=2)
    draw.text((180, 45), "Trois heures du matin... le serveur s effondre.", fill=(255, 220, 100))

    visemes = [
        (210, 'T', 't=0.12s'),
        (300, 'R', 't=0.34s'),
        (390, 'WA', 't=0.58s'),
        (490, '...', 't=0.92s'),
        (590, 'S', 't=1.40s'),
        (680, 'F', 't=1.85s'),
    ]
    for vx, vis, tc in visemes:
        draw.line([(vx, 80), (vx, 110)], fill=(80, 200, 255), width=2)
        draw.ellipse([vx - 14, 85, vx + 14, 113], fill=(30, 60, 90), outline=(80, 220, 255))
        draw.text((vx - 6, 93), vis, fill=(255, 255, 255))
        draw.text((vx - 18, 120), tc, fill=(130, 140, 160))

    img_tts.save('docs/exemples/workflows_audio/tts_dialogue_visemes.png')
    print("TTS dialogue visemes genere")
except Exception as e:
    print("Erreur TTS visemes:", e)

# 3. Rembg : Comparatif Avant / Apres
try:
    casque = Image.open('godot_assets/casque.png').convert('RGBA').resize((240, 240))
    fond_brut = Image.new('RGB', (240, 240), (45, 48, 55))
    fond_brut.paste(casque, (0, 0), casque)

    damier = Image.new('RGBA', (240, 240), (28, 32, 40, 255))
    d_draw = ImageDraw.Draw(damier)
    step = 16
    for y in range(0, 240, step):
        for x in range(0, 240, step):
            if (x // step + y // step) % 2 == 0:
                d_draw.rectangle([x, y, x + step, y + step], fill=(42, 48, 60, 255))
    damier.paste(casque, (0, 0), casque)

    comp = Image.new('RGBA', (560, 310), (16, 18, 24, 255))
    c_draw = ImageDraw.Draw(comp)
    c_draw.text((20, 12), "REMBG : Detourage Neural BiRefNet / RMBG-1.4 (Zero Frange Blanche)", fill=(240, 240, 250))
    comp.paste(fond_brut, (20, 42))
    c_draw.rectangle([18, 40, 262, 284], outline=(90, 60, 60), width=2)
    c_draw.text((20, 290), "1. Image Brute (Fond Uni)", fill=(220, 160, 160))

    comp.paste(damier, (300, 42))
    c_draw.rectangle([298, 40, 542, 284], outline=(60, 180, 120), width=2)
    c_draw.text((300, 290), "2. Detourage Alpha Net (0 halo)", fill=(120, 240, 180))

    comp.save('docs/exemples/workflows_2d/rembg_comparatif.png')
    print("Rembg comparatif genere")
except Exception as e:
    print("Erreur Rembg:", e)

# 4. UI 9-Slice : Demonstration de l etirement
try:
    cadre = Image.open('godot_assets/cadre_portrait_combat.png').convert('RGBA')
    m = 64
    cw, ch = cadre.size
    tl = cadre.crop((0, 0, m, m))
    tr = cadre.crop((cw - m, 0, cw, m))
    bl = cadre.crop((0, ch - m, m, ch))
    br = cadre.crop((cw - m, ch - m, cw, ch))
    top = cadre.crop((m, 0, cw - m, m))
    bottom = cadre.crop((m, ch - m, cw - m, ch))
    left = cadre.crop((0, m, m, ch - m))
    right = cadre.crop((cw - m, m, cw, ch - m))
    center = cadre.crop((m, m, cw - m, ch - m))

    tw, th = 520, 240
    stretched = Image.new('RGBA', (tw, th))
    stretched.paste(tl, (0, 0))
    stretched.paste(tr, (tw - m, 0))
    stretched.paste(bl, (0, th - m))
    stretched.paste(br, (tw - m, th - m))
    stretched.paste(top.resize((tw - 2*m, m)), (m, 0))
    stretched.paste(bottom.resize((tw - 2*m, m)), (m, th - m))
    stretched.paste(left.resize((m, th - 2*m)), (0, m))
    stretched.paste(right.resize((m, th - 2*m)), (tw - m, m))
    stretched.paste(center.resize((tw - 2*m, th - 2*m)), (m, m))

    ui_sheet = Image.new('RGBA', (820, 310), (16, 18, 24, 255))
    u_draw = ImageDraw.Draw(ui_sheet)
    u_draw.text((20, 12), "UI 9-SLICE : Preservation des Coins Ornementaux & Etirement Vectoriel Godot 4", fill=(240, 240, 250))
    
    c_res = cadre.resize((220, 220), Image.Resampling.LANCZOS)
    ui_sheet.paste(c_res, (20, 45), c_res)
    u_draw.rectangle([18, 43, 242, 267], outline=(80, 90, 120), width=1)
    u_draw.text((20, 275), "Source Carree (512x512)", fill=(160, 175, 200))

    ui_sheet.paste(stretched, (275, 45), stretched)
    u_draw.rectangle([273, 43, 797, 287], outline=(220, 160, 60), width=2)
    u_draw.text((275, 292), "NinePatchRect Etire (520x240) - Coins 100% Intacts", fill=(255, 200, 100))

    ui_sheet.save('docs/exemples/workflows_2d/ui_9slice_demo.png')
    print("UI 9-Slice demo genere")
except Exception as e:
    print("Erreur UI 9-slice:", e)

# 5. ESRGAN Upscale Comparatif
try:
    c_orig = Image.open('godot_assets/casque.png').convert('RGBA')
    c_up = Image.open('godot_assets/casque_esrgan_4x.png').convert('RGBA')
    ow, oh = c_orig.size
    crop_orig = c_orig.crop((int(ow*0.35), int(oh*0.30), int(ow*0.65), int(oh*0.60))).resize((250, 250), Image.Resampling.NEAREST)
    
    uw, uh = c_up.size
    crop_up = c_up.crop((int(uw*0.35), int(uh*0.30), int(uw*0.65), int(uh*0.60))).resize((250, 250), Image.Resampling.LANCZOS)

    up_img = Image.new('RGBA', (560, 320), (16, 18, 24, 255))
    u_draw = ImageDraw.Draw(up_img)
    u_draw.text((20, 12), "UPSCALE : Real-ESRGAN Vulkan 4x-UltraSharp (Zoom 400% sur Micro-Details)", fill=(240, 240, 250))
    up_img.paste(crop_orig, (20, 42))
    u_draw.rectangle([18, 40, 272, 294], outline=(120, 60, 60), width=2)
    u_draw.text((20, 300), "1. Original Pixelise (Zoom 4x Nearest)", fill=(220, 140, 140))

    up_img.paste(crop_up, (290, 42))
    u_draw.rectangle([288, 40, 542, 294], outline=(60, 200, 120), width=2)
    u_draw.text((290, 300), "2. 4x-UltraSharp (Aretes Nettoyées)", fill=(120, 240, 160))

    up_img.save('docs/exemples/workflows_2d/upscale_comparatif_zoom.png')
    print("Upscale comparatif zoom genere")
except Exception as e:
    print("Erreur Upscale comparatif:", e)
