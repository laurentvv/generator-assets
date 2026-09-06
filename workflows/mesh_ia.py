#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Mesh IA : objet 3D volumique depuis une image ou un prompt
(TRELLIS.2-4B GGUF via trellis.cpp, backend Vulkan). Validé par l'utilisateur
le 2026-09-06 sur le casque du dépôt (res 512 = 10 min 44 s, res 1024 = 55 min).

Contrairement à mesh3d (formes paramétriques extrudées), ce workflow produit un
vrai volume fermé inféré par IA, avec textures PBR — casque, statues, créatures,
props complexes. Sortie : GLB + rendus de contrôle Blender + planche récap.
"""

import os
import time
from typing import Any, Dict

from core.config import slugifier_texte
from core.mesh_ia import (
    DUREES_ESTIMEES,
    assembler_planche,
    generer_mesh_trellis,
    reduire_mesh_blender,
    rendre_controle_blender,
    verifier_trellis,
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class MeshIaWorkflow(BaseWorkflow):
    """Image ou prompt → objet 3D IA (.glb PBR) via TRELLIS.2 GGUF (Vulkan)."""

    name = "mesh_ia"
    description = ("Objet 3D IA volumique depuis une image ou un prompt "
                   "(TRELLIS.2-4B GGUF, Vulkan) : GLB PBR + rendus de contrôle Blender")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_image = params.get("input")
        prompt = params.get("prompt")
        if not input_image and not prompt:
            raise ValueError("Fournir -i <image.png> ou un prompt (l'image source sera générée par Flux puis détourée).")

        ok, manquants = verifier_trellis()
        if not ok:
            raise EnvironmentError("Composants TRELLIS.2 manquants : " + " ; ".join(manquants))

        res = int(params.get("res") or 512)
        if res not in (512, 1024, 1536):
            raise ValueError(f"Résolution {res} invalide (512, 1024 ou 1536).")
        seed = params.get("seed")
        if seed is not None:
            seed = int(seed)

        nom_base = slugifier_texte(
            params.get("output") or (prompt if prompt else os.path.splitext(os.path.basename(input_image))[0])
        )[:60]
        dossier = os.path.join("output", "mesh_ia", nom_base)
        os.makedirs(dossier, exist_ok=True)

        # 1. Image source : fournie, ou générée + détourée par le workflow generate
        #    (une image pré-mattée conserve son alpha → pas de cutout BiRefNet côté trellis).
        if not input_image:
            self.log("Génération de l'image source (Flux Vulkan) + détourage…", "🖼️")
            wf_gen = WorkflowRegistry.get("generate")(self.config)
            params_gen = dict(params)
            params_gen["output"] = nom_base
            params_gen["output_dir"] = dossier
            res_gen = wf_gen.run(params_gen)
            input_image = res_gen["output_path"]
        elif not os.path.exists(input_image):
            raise FileNotFoundError(f"Image source introuvable : {input_image}")

        # 2. TRELLIS.2 : image → GLB PBR
        estime = DUREES_ESTIMEES.get(res, "?")
        self.log(f"TRELLIS.2 image → 3D (res {res}, {estime} sur RX 6950 XT) — sortie : {dossier}", "🧊")
        t0 = time.time()
        resultat = generer_mesh_trellis(
            image_path=input_image,
            output_dir=dossier,
            nom_base=nom_base,
            res=res,
            seed=seed,
        )
        mm, ss = divmod(int(resultat["duree_s"]), 60)
        self.log(f"GLB PBR généré en {mm} min {ss:02d} s : {resultat['glb']}", "✅")

        # 3. Réduction de maillage OPTIONNELLE pour le runtime (master conservé)
        #    trellis sort 150-300 k faces : passer --faces-cible N (ex: 30000)
        #    pour un GLB « jeu » décimé ; défaut = pas de réduction.
        faces_cible = params.get("faces_cible")
        faces_cible = 0 if faces_cible is None else int(faces_cible)
        glb_controle = resultat["glb"]
        if faces_cible > 0:
            glb_jeu = os.path.join(dossier, f"{nom_base}_{res}_jeu.glb")
            red = reduire_mesh_blender(resultat["glb"], glb_jeu, faces_cible)
            if red:
                resultat["glb_jeu"] = red["glb"]
                resultat["faces_avant"] = red["faces_avant"]
                resultat["faces_apres"] = red["faces_apres"]
                self.log(f"Réduction : {red['faces_avant']} → {red['faces_apres']} faces "
                         f"(cible {faces_cible}) : {red['glb']}", "📉")
                glb_controle = red["glb"]

        # 4. Rendus de contrôle Blender + planche récapitulative
        vues = rendre_controle_blender(glb_controle, dossier, f"{nom_base}_{res}")
        planche = None
        if len(vues) == 4:
            planche = assembler_planche(
                source_png=input_image,
                vues=vues,
                base_png=resultat.get("base_png"),
                sortie=os.path.join(dossier, f"{nom_base}_{res}_planche.png"),
            )
            self.log(f"Planche de contrôle : {planche}", "📷")

        taille_mo = os.path.getsize(resultat["glb"]) / (1024 * 1024)
        self.log(f"Objet prêt pour Godot : {resultat['glb']} ({taille_mo:.1f} Mo, res {res})", "🎮")

        resultat.update({
            "vues": vues,
            "planche": planche,
            "image_source": input_image,
            "dossier": dossier,
        })
        return resultat
