# Retarget local : animations du loup Quaternius (ref, 51 os) -> notre rig Rigify.
# Principe : delta de rotation MONDE de chaque os ref (pose vs rest), applique au
# rest de l'os cible mappe ; echantillonne frame par frame puis cuit en quaternions.
# Translation ignoree (le reste sur place) : le sol ne glisse pas, le gallop reste lisible.
#
# Usage : blender -b output/test_rig/scenes/wolf_rigify.blend -P retarget_quaternius.py -- <action_ref> <sortie_blend>

import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
action_ref_nom = argv[0]
sortie = os.path.abspath(argv[1])

REF_BLEND = r"C:\GIT\generator-assets\output\test_rig\meshes\quaternius_animaux\Wolf_rigge.blend"

scene = bpy.context.scene
rig = bpy.data.objects["rig_loup"]

# ---- import de l'armature de reference + ses actions ----
objets_avant_import = set(bpy.data.objects.keys())
with bpy.data.libraries.load(REF_BLEND, link=False) as (src, dst):
    dst.objects = list(src.objects)  # import COMPLET : sinon les contraintes IK sont cassees
    dst.actions = list(src.actions)
ref = bpy.data.objects["AnimalArmature"]
ref.hide_set(False)
ref.select_set(False)
# libraries.load ne lie PAS les objets a la collection de la scene : sans lien,
# le depsgraph n'evalue ni l'animation ni les contraintes IK (pose figee au rest)
scene.collection.objects.link(ref)
bpy.context.view_layer.update()
print("REF_OBJS:", [o for o in bpy.data.objects.keys() if o not in objets_avant_import])
print("REF_ACTIONS:", len(bpy.data.actions))

# ---- mapping ref -> DEF de notre rig (explicite, verifie sur les listes reelles) ----
# Notre chaine DEF-spine : spine = bout de queue, .001-.002 queue, .003 arriere,
# .004-.006 torse, .007-.008 garrot, .009-.010 cou, .011 tete.
# Os ref ignores : IK*/FF*/PoleTarget* (helpers), Ear*.001+ (nos DEF s'arretent a 1).
MAPPING = {
    "Torso": "DEF-spine.004",
    "Torso2": "DEF-spine.005",
    "Torso3": "DEF-spine.006",
    "Neck1": "DEF-spine.008",
    "Neck2": "DEF-spine.009",
    "Neck3": "DEF-spine.010",
    "Head": "DEF-spine.011",
    "Tail1": "DEF-spine.003",
    "Tail2": "DEF-spine.002",
    "Tail3": "DEF-spine.001",
    "Tail4": "DEF-spine",
    "FrontShoulder.L": "DEF-shoulder.L",
    "FrontShoulder.R": "DEF-shoulder.R",
    "FrontUpperLeg.L": "DEF-front_thigh.L",
    "FrontUpperLeg.R": "DEF-front_thigh.R",
    "FrontLowerLeg.L": "DEF-front_shin.L",
    "FrontLowerLeg.R": "DEF-front_shin.R",
    "BackShoulder.L": "DEF-pelvis.L",
    "BackShoulder.R": "DEF-pelvis.R",
    "BackLeg.L": "DEF-thigh.L",
    "BackLeg.R": "DEF-thigh.R",
    "BackUpperLeg.L": "DEF-shin.L",
    "BackUpperLeg.R": "DEF-shin.R",
    "BackLowerLeg.L": "DEF-foot.L",
    "BackLowerLeg.R": "DEF-foot.R",
    "Ear1.L": "DEF-ear.L",
    "Ear1.R": "DEF-ear.R",
}

ref_noms = [b.name for b in ref.pose.bones]
print("REF_BONES:", ref_noms)

manquants = [t for t in MAPPING.values() if t not in rig.pose.bones]
assert not manquants, "DEF absents dans notre rig : %s" % manquants

# Les DEF Rigify sont contraints par la chaine MCH (controles au rest) : les
# contraintes ecraseraient nos cles. On les desactive sur TOUS les DEF.
nb_mutees = 0
for pb in rig.pose.bones:
    if pb.name.startswith("DEF-"):
        for c in pb.constraints:
            if c.type not in {"VISUAL_TRANSFORM"}:
                c.mute = True
                nb_mutees += 1
print("CONTRAINTES_MUTEES:", nb_mutees)

# Rigify dedouble les deformateurs (DEF-x + DEF-x.001) : le meme delta
# s'applique aux deux, sinon la moitie du membre reste au rest.
# Structure : liste de paires (os_ref, os_cible) — PAS de clés fantômes.
paires = list(MAPPING.items())
for os_ref, os_cible in list(MAPPING.items()):
    if os_cible + ".001" in rig.pose.bones:
        paires.append((os_ref, os_cible + ".001"))

print("MAPPING_FINAL(%d paires)" % len(paires))

# ---- bake ----
action_ref = bpy.data.actions.get(action_ref_nom)
assert action_ref, "action absente : " + action_ref_nom
# L'evaluation frame_set des actions importees (legacy 2.79 -> slots 5.2) ne se
# fait PAS en headless : on evalue les fcurves a la main, os par os.
canalbag = None
for layer in action_ref.layers:
    for strip in layer.strips:
        for cb in strip.channelbags:
            canalbag = cb
assert canalbag is not None, "action sans channelbag"
courbes = {}
for fc in canalbag.fcurves:
    courbes.setdefault(fc.data_path, {})[fc.array_index] = fc
print("FCURVES_MANUELLES:", len(canalbag.fcurves), "| os touches:", len(courbes))

# rest du ref en pose neutre (on ecrase la pose avec les fcurves a chaque frame)
ref.animation_data_create()
ref.animation_data.action = None
bpy.context.view_layer.update()
rest_ref = {b.name: b.bone.matrix_local.copy() for b in ref.pose.bones}
rest_tgt = {b.name: b.bone.matrix_local.copy() for b in rig.pose.bones}


def pose_ref_manuelle(frame):
    """Pose de la ref a `frame` reconstruite depuis les fcurves (sans frame_set).

    Le rig Quaternius est un rig IK : les actions animent les CONTROLLEURS IK
    en LOCATION ; les os des membres suivent via contraintes IK resolues par le
    depsgraph. On applique donc locations ET rotations, puis on laisse le
    solveur travailler dans update().
    """
    for chemin_os, canaux in courbes.items():
        nom_os = chemin_os.split('"')[1]
        pb = ref.pose.bones.get(nom_os)
        if pb is None:
            continue
        if "location" in chemin_os and {0, 1, 2} <= canaux.keys():
            pb.location = [canaux[i].evaluate(frame) for i in range(3)]
        elif "rotation_quaternion" in chemin_os and {0, 1, 2, 3} <= canaux.keys():
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = Quaternion(
                [canaux[i].evaluate(frame) for i in range(4)])
        elif "rotation_euler" in chemin_os and {0, 1, 2} <= canaux.keys():
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = [canaux[i].evaluate(frame) for i in range(3)]
    ref.update_tag()  # force la re-evaluation des contraintes IK en headless
    bpy.context.view_layer.update()
    if frame == 9:
        ik = ref.pose.bones.get('IKFrontLeg.L')
        haut = ref.pose.bones.get('FrontUpperLeg.L')
        if ik:
            print('DBG9 ik.location=', tuple(round(v, 3) for v in ik.location),
                  'lock=', list(ik.lock_location),
                  'nb_contraintes_sur_FrontLower=', len(ref.pose.bones['FrontLowerLeg.L'].constraints))
        if haut:
            print('DBG9 FrontUpper.matrix=', tuple(round(v, 3) for v in haut.matrix.translation))


debut, fin = int(action_ref.frame_range[0]), int(action_ref.frame_range[1])
print("BAKE %s frames %d..%d" % (action_ref_nom, debut, fin))

notre_action = bpy.data.actions.new("RETARGET_%s" % action_ref_nom)
rest_body_z = ref.pose.bones["Body"].bone.matrix_local.translation.z if "Body" in ref.pose.bones else None
echelle = 0.25
rig.animation_data_create()
rig.animation_data.action = notre_action

# pose rest de reference memoire
rest_ref = {b.name: b.bone.matrix_local.copy() for b in ref.pose.bones}
rest_tgt = {b.name: b.bone.matrix_local.copy() for b in rig.pose.bones}

ordre = []
for nom_ref, tgt_nom in paires:
    pb = rig.pose.bones[tgt_nom]
    profondeur = 0
    p = pb
    while p.parent:
        profondeur += 1
        p = p.parent
    ordre.append((profondeur, nom_ref, tgt_nom))
ordre.sort(key=lambda t: (t[0], t[1], t[2]))

for f in range(debut, fin + 1):
    pose_ref_manuelle(f)
    for _, nom_ref, tgt_nom in ordre:
        pb_ref = ref.pose.bones[nom_ref]
        pb_tgt = rig.pose.bones[tgt_nom]
        # delta monde du ref (pose vs rest), armatures identites -> monde = armature
        q_ref_pose = pb_ref.matrix.to_quaternion()
        q_ref_rest = rest_ref[nom_ref].to_quaternion()
        q_delta = q_ref_pose @ q_ref_rest.inverted()
        # frame cible en espace armature, convertie en basis locale du bone
        q_frame = q_delta @ rest_tgt[tgt_nom].to_quaternion()
        q_basis = rest_tgt[tgt_nom].to_quaternion().inverted() @ q_frame
        pb_tgt.rotation_mode = "QUATERNION"
        pb_tgt.rotation_quaternion = q_basis
        pb_tgt.keyframe_insert(data_path="rotation_quaternion", frame=f)

print("RETARGET_PRET:%s" % sortie)
