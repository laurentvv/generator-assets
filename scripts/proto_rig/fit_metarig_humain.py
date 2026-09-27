"""Wave 2A — Agentic fit of the Rigify metarig onto the MPFB Body (T-pose).

Repositions the key joints of the metarig onto the landmarks measured on the mesh
(Z slices), aligns the rolls (palms down, kneecaps forward),
translates palms/fingers along with the hand. Then an x-ray capture for verification.

Landmarks measured on 2026-09-18 on humain_a_mesh.blend (Body 14517 vertices):
feet Z=0, ankles 0.07, hips (±0.09, 0.72), neck base 1.13, head top 1.381,
shoulders (±0.185, 0.78), wrists ±0.365, hand tips ±0.4225, face -Y.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_client import envoyer  # noqa: E402

CODE_FIT = r"""
import bpy
from mathutils import Vector

# ---- mesh landmarks (meters, world) ----
CHEVILLE_Z = 0.07
HANCHE = (0.09, 0.0, 0.72)
GENOU_Z = 0.40
BASSIN_Z = 0.74
COU_Z = 1.13
EPAULE = (0.185, 0.0, 0.78)
POIGNET_X = 0.365
BOUT_MAIN_X = 0.4225
COUDE_X = (EPAULE[0] + POIGNET_X) / 2
ORTEIL_DEPART_Y = -0.055
ORTEIL_BOUT_Y = -0.115
PIED_Z = 0.015

meta = bpy.data.objects['metarig']
bpy.context.view_layer.objects.active = meta
bpy.ops.object.mode_set(mode='EDIT')
eb = meta.data.edit_bones

def os_(nom):
    return eb.get(nom)

def placer(nom, tete, queue):
    b = os_(nom)
    if b is None:
        print('MISSING:', nom)
        return
    b.head = Vector(tete)
    b.tail = Vector(queue)

def rouler(nom, cible):
    b = os_(nom)
    if b is not None:
        b.align_roll(Vector(cible).normalized())

# delta of the hand.L head to translate palms + fingers
delta_x = EPAULE[0] * 1.0  # recomputed below from the old position
old_hand = os_('hand.L')
ancien_x = old_hand.head.x if old_hand else 0.66
nouveau_x = POIGNET_X
delta = nouveau_x - ancien_x

# ---- spine: 7 bones spread between pelvis and neck ----
n_col = 7
z0, z1 = BASSIN_Z, COU_Z
pas = (z1 - z0) / n_col
for i in range(n_col):
    nom = 'spine' if i == 0 else 'spine.%03d' % i
    placer(nom, (0.0, 0.0, z0 + pas * i), (0.0, 0.0, z0 + pas * (i + 1)))
    rouler(nom, (0, -1, 0))

# ---- head ('face' bone) ----
placer('face', (0.0, 0.01, COU_Z + 0.02), (0.0, 0.0, 1.31))

# ---- pelvis ----
placer('pelvis.L', (0.0, 0.0, BASSIN_Z), (HANCHE[0], -0.04, BASSIN_Z + 0.14))
placer('pelvis.R', (0.0, 0.0, BASSIN_Z), (-HANCHE[0], -0.04, BASSIN_Z + 0.14))

# ---- legs ----
for c, s in (('L', 1), ('R', -1)):
    placer('thigh.%s' % c, (s * HANCHE[0], 0.0, HANCHE[2]), (s * HANCHE[0], 0.0, GENOU_Z))
    placer('shin.%s' % c, (s * HANCHE[0], 0.0, GENOU_Z), (s * HANCHE[0], 0.0, CHEVILLE_Z))
    placer('foot.%s' % c, (s * HANCHE[0], 0.0, CHEVILLE_Z), (s * HANCHE[0], ORTEIL_DEPART_Y, PIED_Z))
    placer('toe.%s' % c, (s * HANCHE[0], ORTEIL_DEPART_Y, PIED_Z), (s * HANCHE[0], ORTEIL_BOUT_Y, PIED_Z))
    placer('heel.02.%s' % c, (s * HANCHE[0], 0.02, CHEVILLE_Z), (s * HANCHE[0], 0.05, 0.005))
    for nom in ('thigh.%s', 'shin.%s'):
        rouler(nom % c, (0, -1, 0))

# ---- arms in strict T-pose (palms down) ----
for c, s in (('L', 1), ('R', -1)):
    placer('shoulder.%s' % c, (s * 0.03, -0.01, EPAULE[2] + 0.01), (s * EPAULE[0], 0.0, EPAULE[2]))
    placer('upper_arm.%s' % c, (s * EPAULE[0], 0.0, EPAULE[2]), (s * COUDE_X, 0.0, EPAULE[2]))
    placer('forearm.%s' % c, (s * COUDE_X, 0.0, EPAULE[2]), (s * POIGNET_X, 0.0, EPAULE[2]))
    placer('hand.%s' % c, (s * POIGNET_X, 0.0, EPAULE[2]), (s * BOUT_MAIN_X, 0.0, EPAULE[2]))
    for nom in ('upper_arm.%s', 'forearm.%s', 'hand.%s'):
        rouler(nom % c, (0, 0, -1))
    # palms + fingers + thumb: translation tied to the hand
    for b in eb:
        if c in b.name and any(b.name.startswith(p) for p in ('palm.', 'f_', 'thumb.')):
            b.head += Vector((s * delta, 0, 0))
            b.tail += Vector((s * delta, 0, 0))
    # approximate eyes and temples (head center Z~1.26, nose depth -Y)
    placer('eye.%s' % c, (s * 0.032, -0.088, 1.255), (s * 0.032, -0.085, 1.265))
    placer('temple.%s' % c, (s * 0.072, 0.015, 1.27), (s * 0.074, 0.02, 1.29))

bpy.ops.object.mode_set(mode='OBJECT')
meta.data.pose_position = 'REST'
bpy.context.view_layer.update()

# x-ray display for verification
meta.show_in_front = True
meta.display_type = 'WIRE'
print('FIT_OK')
"""

CODE_XRAY = """
import bpy
for o in bpy.context.scene.objects:
    if o.type == 'MESH':
        o.color = (0.65, 0.72, 0.8, 1.0)
bpy.context.view_layer.update()
print('XRAY_PRET')
"""


def main() -> int:
    reponse = envoyer("execute_code", {"code": CODE_FIT})
    brut = reponse.get("result", "")
    texte = str(brut.get("result", "")) if isinstance(brut, dict) else str(brut)
    print(texte.strip())
    if "FIT_OK" not in texte:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
