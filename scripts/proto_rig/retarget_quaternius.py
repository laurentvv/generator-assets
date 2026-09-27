# Local retarget: animations of the Quaternius wolf (ref, 51 bones) -> our Rigify rig.
# Principle: WORLD rotation delta of each ref bone (pose vs rest), applied to the
# rest of the mapped target bone; sampled frame by frame then baked into quaternions.
# Translation ignored (the rest stays in place): the ground does not slide, the gallop stays readable.
#
# Usage: blender -b output/test_rig/scenes/wolf_rigify.blend -P retarget_quaternius.py -- <action_ref> <sortie_blend>

import os
import sys

import bpy
from mathutils import Quaternion

argv = sys.argv[sys.argv.index("--") + 1:]
action_ref_nom = argv[0]
sortie = os.path.abspath(argv[1])

REF_BLEND = r"C:\GIT\generator-assets\output\test_rig\meshes\quaternius_animaux\Wolf_rigge.blend"

scene = bpy.context.scene
rig = bpy.data.objects["rig_loup"]

# ---- import of the reference armature + its actions ----
objets_avant_import = set(bpy.data.objects.keys())
with bpy.data.libraries.load(REF_BLEND, link=False) as (src, dst):
    dst.objects = list(src.objects)  # FULL import: otherwise the IK constraints are broken
    dst.actions = list(src.actions)
ref = bpy.data.objects["AnimalArmature"]
ref.hide_set(False)
ref.select_set(False)
# libraries.load does NOT link the objects to the scene collection: without a link,
# the depsgraph evaluates neither the animation nor the IK constraints (pose frozen at rest)
scene.collection.objects.link(ref)
bpy.context.view_layer.update()
print("REF_OBJS:", [o for o in bpy.data.objects.keys() if o not in objets_avant_import])
print("REF_ACTIONS:", len(bpy.data.actions))

# ---- mapping ref -> DEF of our rig (explicit, checked against the real lists) ----
# Our DEF-spine chain: spine = tail tip, .001-.002 tail, .003 rear,
# .004-.006 torso, .007-.008 withers, .009-.010 neck, .011 head.
# Ignored ref bones: IK*/FF*/PoleTarget* (helpers), Ear*.001+ (our DEFs stop at 1).
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
assert not manquants, "DEF missing from our rig: %s" % manquants

# The Rigify DEFs are driven by the MCH chain (controls at rest): the
# constraints would override our keys. We disable them on ALL the DEFs.
nb_mutees = 0
for pb in rig.pose.bones:
    if pb.name.startswith("DEF-"):
        for c in pb.constraints:
            if c.type not in {"VISUAL_TRANSFORM"}:
                c.mute = True
                nb_mutees += 1
print("MUTED_CONSTRAINTS:", nb_mutees)

# Rigify duplicates the deformers (DEF-x + DEF-x.001): the same delta
# applies to both, otherwise half of the limb stays at rest.
# Structure: list of (ref_bone, target_bone) pairs — NO ghost keys.
paires = list(MAPPING.items())
for os_ref, os_cible in list(MAPPING.items()):
    if os_cible + ".001" in rig.pose.bones:
        paires.append((os_ref, os_cible + ".001"))

print("MAPPING_FINAL(%d paires)" % len(paires))

# ---- bake ----
action_ref = bpy.data.actions.get(action_ref_nom)
assert action_ref, "missing action: " + action_ref_nom
# The frame_set evaluation of the imported actions (legacy 2.79 -> 5.2 slots) does
# NOT happen headless: we evaluate the fcurves by hand, bone by bone.
canalbag = None
for layer in action_ref.layers:
    for strip in layer.strips:
        for cb in strip.channelbags:
            canalbag = cb
assert canalbag is not None, "action without channelbag"
courbes = {}
for fc in canalbag.fcurves:
    courbes.setdefault(fc.data_path, {})[fc.array_index] = fc
print("MANUAL_FCURVES:", len(canalbag.fcurves), "| bones touched:", len(courbes))

# ref rest in neutral pose (we overwrite the pose with the fcurves at each frame)
ref.animation_data_create()
ref.animation_data.action = None
bpy.context.view_layer.update()
rest_ref = {b.name: b.bone.matrix_local.copy() for b in ref.pose.bones}
rest_tgt = {b.name: b.bone.matrix_local.copy() for b in rig.pose.bones}


def pose_ref_manuelle(frame):
    """Pose of the ref at `frame` rebuilt from the fcurves (without frame_set).

    The Quaternius rig is an IK rig: the actions animate the IK CONTROLLERS
    in LOCATION; the limb bones follow via IK constraints solved by the
    depsgraph. We therefore apply locations AND rotations, then let the
    solver work in update().
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
    ref.update_tag()  # forces the re-evaluation of the IK constraints headless
    bpy.context.view_layer.update()
    if frame == 9:
        ik = ref.pose.bones.get('IKFrontLeg.L')
        haut = ref.pose.bones.get('FrontUpperLeg.L')
        if ik:
            print('DBG9 ik.location=', tuple(round(v, 3) for v in ik.location),
                  'lock=', list(ik.lock_location),
                  'nb_constraints_on_FrontLower=', len(ref.pose.bones['FrontLowerLeg.L'].constraints))
        if haut:
            print('DBG9 FrontUpper.matrix=', tuple(round(v, 3) for v in haut.matrix.translation))


debut, fin = int(action_ref.frame_range[0]), int(action_ref.frame_range[1])
print("BAKE %s frames %d..%d" % (action_ref_nom, debut, fin))

notre_action = bpy.data.actions.new("RETARGET_%s" % action_ref_nom)
rest_body_z = ref.pose.bones["Body"].bone.matrix_local.translation.z if "Body" in ref.pose.bones else None
echelle = 0.25
rig.animation_data_create()
rig.animation_data.action = notre_action

# reference rest pose kept in memory
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
        # world delta of the ref (pose vs rest), armatures identity -> world = armature
        q_ref_pose = pb_ref.matrix.to_quaternion()
        q_ref_rest = rest_ref[nom_ref].to_quaternion()
        q_delta = q_ref_pose @ q_ref_rest.inverted()
        # target frame in armature space, converted to the bone's local basis
        q_frame = q_delta @ rest_tgt[tgt_nom].to_quaternion()
        q_basis = rest_tgt[tgt_nom].to_quaternion().inverted() @ q_frame
        pb_tgt.rotation_mode = "QUATERNION"
        pb_tgt.rotation_quaternion = q_basis
        pb_tgt.keyframe_insert(data_path="rotation_quaternion", frame=f)

print("RETARGET_PRET:%s" % sortie)
