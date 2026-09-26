#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prototype d'animation de personnage par ControlNet OpenPose (route 2D frame par frame).

Recette (validée statiquement le 2026-09-26, cf. MEMORY_BANK §1.29) :
- chorégraphie : action Blender exportée en keypoints COCO 18 (exporter_squelettes_punch.py),
  projection VUE DE FACE avec transformation FIXE sur toute la séquence (pas de saut d'échelle) ;
- cohérence d'apparence : topologie ÉTOILE — chaque frame est dérivée de la frame 0 en
  img2img (strength 0.55) + ControlNet de pose (strength 0.9), même prompt, même seed.
  (Le workflow « ip_adapter » du dépôt verrouille le style par prompt, pas par image :
  pas de vrai IP-Adapter en local, l'img2img étoile est la parade robuste zéro téléchargement.)

Usage : uv run python scripts/proto_anim_controlnet/generer_boucle_punch.py [--debut 0 --fin 5]
Reprenable : les frames déjà produites sont sautées.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PIL import Image

from core.diffusion import generer_image_vulkan
from core.pose_ops import dessiner_squelette_openpose

DOSSIER = os.path.join("output", "test_anim_controlnet")
CHEMIN_POINTS = os.path.join(DOSSIER, "points_punch.json")
SDXL = r"C:/Modeles_LLM/juggernautXL_ragnarok.safetensors"
CONTROLNET = r"C:/Modeles_LLM/controlnet_openpose_sdxl_xinsir.safetensors"
IP_ADAPTER = r"C:/Modeles_LLM/ip-adapter-plus_sdxl_vit-h.safetensors"
CLIP_VISION = r"C:/Modeles_LLM/clip_vision_h.safetensors"
PROMPT = ("fantasy knight in shining steel plate armor, sword slash attack, dynamic action, "
          "full body, game character sprite, isolated on plain white background")
L, H = 768, 1024
MARGE = 0.10          # fraction de marge autour du bbox de la séquence
FORCE_POSE = 0.9      # --control-strength (recette validée)
FORCE_APPARENCE = 0.55  # img2img depuis la frame 0 (topologie étoile)
FORCE_IP = 0.7        # --ip-adapter-strength : verrou d'apparence sans ancrer la pose
REFERENCE_APPARENCE = os.path.join(DOSSIER, "reference_apparence.png")  # chevalier statique validé
SEED = 42


def transformation_fixe(poses):
    """Bbox global de la séquence -> échelle/centre constants pour toutes les frames.

    Projection VUE DE PROFIL : image_x = -Y monde (l'action se lit latéralement, un punch
    de face est foreshortened et illisible en 2D), image_y = -Z monde (Z up -> y image).
    """
    tous = [p for pose in poses.values() for p in pose.values()]
    ymin, ymax = min(p[1] for p in tous), max(p[1] for p in tous)
    zmin, zmax = min(p[2] for p in tous), max(p[2] for p in tous)
    echelle = min(L * (1 - 2 * MARGE) / (ymax - ymin), H * (1 - 2 * MARGE) / (zmax - zmin))
    cy, cz = (ymin + ymax) / 2, (zmin + zmax) / 2
    ox = L / 2 + cy * echelle   # image_x = ox - y * echelle
    oy = H / 2 + cz * echelle   # image_y = oy - z * echelle

    def projeter(p):
        return ((ox - p[1] * echelle) / L, (oy - p[2] * echelle) / H)

    return projeter


def dessiner_tous(poses):
    projeter = transformation_fixe(poses)
    dossier_skel = os.path.join(DOSSIER, "skeletons")
    os.makedirs(dossier_skel, exist_ok=True)
    chemins = {}
    for cle in sorted(poses):
        chemin = os.path.join(dossier_skel, f"skel_{cle}.png")
        if not os.path.exists(chemin):
            points = {k: projeter(v) for k, v in poses[cle].items()}
            dessiner_squelette_openpose(points, largeur=L, hauteur=H).save(chemin, "PNG")
        chemins[cle] = chemin
    return chemins


def generer(chemins, debut, fin):
    cles = sorted(chemins)[debut:fin]
    for cle in cles:
        chemin_frame = os.path.join(DOSSIER, f"frame_{cle}.png")
        if os.path.exists(chemin_frame):
            print(f"frame {cle} déjà produite, sautée")
            continue
        t0 = time.time()
        kw = dict(
            prompt=PROMPT, sd_model=SDXL, control_image=chemins[cle],
            control_net=CONTROLNET, control_strength=FORCE_POSE,
            width=L, height=H, steps=25, seed=SEED,
        )
        if cle == "00" and not os.path.exists(REFERENCE_APPARENCE):
            print(f"[{cle}] txt2img + ControlNet (passe 1)...")
        else:
            # IP-Adapter (apparence verrouillée sur la référence) + ControlNet (pose) :
            # l'img2img étoile ancre la pose de départ (strength 0.55 = pose figée),
            # le txt2img + IP-Adapter laisse le ControlNet déplacer les membres.
            # Passe 2 : référence = frame médiane de la passe 1 pour TOUTES les frames
            # (y compris 00) -> apparence homogène sur toute la boucle.
            kw.update(ip_adapter=IP_ADAPTER,
                      ip_adapter_image=REFERENCE_APPARENCE,
                      ip_adapter_strength=FORCE_IP,
                      clip_vision=CLIP_VISION)
            print(f"[{cle}] txt2img + ControlNet + IP-Adapter(ref)...")
        img = generer_image_vulkan(**kw)
        img.save(chemin_frame, "PNG")
        print(f"[{cle}] OK en {time.time() - t0:.0f}s -> {chemin_frame}")


def assembler():
    fichiers = sorted(chemins_cles())
    if len(fichiers) < 12:
        return
    frames = [Image.open(os.path.join(DOSSIER, f)).convert("RGB") for f in fichiers]
    # GIF boucle ping-pong (l'action Punch n'est pas cyclique : 0..11..1 évite le saut)
    aller = frames + frames[-2:0:-1]
    aller[0].save(os.path.join(DOSSIER, "boucle_punch.gif"), save_all=True,
                  append_images=aller[1:], duration=120, loop=0)
    # bande horizontale
    bande = Image.new("RGB", (L // 2 * len(frames), H // 2), "white")
    for i, f in enumerate(frames):
        bande.paste(f.resize((L // 2, H // 2)), (i * L // 2, 0))
    bande.save(os.path.join(DOSSIER, "bande_punch.png"), "PNG")
    print("GIF + bande assemblés")


def chemins_cles():
    return [f for f in os.listdir(DOSSIER)
            if f.startswith("frame_") and f.endswith(".png")]


def main():
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--debut", type=int, default=0)
    parseur.add_argument("--fin", type=int, default=12)
    args = parseur.parse_args()

    with open(CHEMIN_POINTS, encoding="utf-8") as f:
        poses = json.load(f)["poses"]
    chemins = dessiner_tous(poses)
    generer(chemins, args.debut, args.fin)
    if len(chemins_cles()) >= 12:
        assembler()


if __name__ == "__main__":
    main()
