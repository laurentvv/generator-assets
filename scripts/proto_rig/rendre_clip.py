# Clip animé d'un rig — rendu EEVEE headless + encodage MP4.
# Pattern turntable.py (proto_blender_skills) : caméra orbitale + 3 points,
# mais l'ANIMATION du sujet est le sujet du plan (trot loup / salut humain).
#
# Usage :
#   blender -b <blend> -P rendre_clip.py -- <mp4_out> <anim> [frames=72] [fps=24] [res=1280]
#   anim ∈ {loup, humain, none}

import math
import os
import shutil
import subprocess
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
mp4_out = os.path.abspath(argv[0])
anim = argv[1] if len(argv) > 1 else "none"
nb_frames = int(argv[2]) if len(argv) > 2 else 72
fps = int(argv[3]) if len(argv) > 3 else 24
res = int(argv[4]) if len(argv) > 4 else 1280
CAM_FIXE = "--fixe" in argv   # camera fixe (le mouvement du sujet est seul en scene)
BOUCLE = "--boucle" in argv   # boucle l'action cuit du fichier (retarget)

scene = bpy.context.scene
rig = next((o for o in scene.objects if o.type == "ARMATURE" and "metarig" not in o.name.lower()), None)
assert rig, "aucune armature dans le fichier"

# plage de l'action cuite (pour --boucle)
action_debut, action_fin = 1, 1
if BOUCLE and rig.animation_data and rig.animation_data.action:
    fr = rig.animation_data.action.frame_range
    action_debut, action_fin = int(fr[0]), int(fr[1])
    print("BOUCLE action %s : frames %d..%d" % (rig.animation_data.action.name, action_debut, action_fin))


def trouver_ffmpeg():
    for c in (shutil.which("ffmpeg"), r"C:\ffmpeg\dist\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if c:
            return c
    raise RuntimeError("ffmpeg introuvable")


# ---------------------------------------------------------------- animations
def poser(rig, nom, chemin, angles):
    pb = rig.pose.bones.get(nom)
    if pb is None:
        print("ANIM: os absent", nom)
        return
    pb.rotation_mode = chemin or "XYZ"
    pb.rotation_euler = angles
    pb.keyframe_insert(data_path="rotation_euler", frame=scene.frame_current)


def basculer_fk(rig):
    """Passe les MEMBRES de Rigify en mode FK (slider IK_FK=1).

    Filtre strict sur les os *_parent de membres : basculer aussi la colonne
    (torso/neck) plie la chaine torse-tete (blob d'epaules constate).
    """
    for nom, pb in rig.pose.bones.items():
        if "IK_FK" in pb and ("arm_parent" in nom or "thigh_parent" in nom):
            pb["IK_FK"] = 1.0
            pb.keyframe_insert(data_path='["IK_FK"]', frame=scene.frame_current)


def animer_loup(rig, n):
    """Trot sur place AMPLIFIE : diagonales marquees, bob net, queue en vague."""
    scene.frame_set(1)
    basculer_fk(rig)
    per = 36.0  # frames par cycle
    for f in range(1, n + 1):
        scene.frame_set(f)
        t = 2 * math.pi * f / per
        # pattes : swing X ample, diagonal front.L + rear.R
        poser(rig, "front_thigh_fk.L", "XYZ", (-0.30 + 0.75 * math.sin(t), 0, 0))
        poser(rig, "front_shin_fk.L", "XYZ", (0.85 - 0.70 * math.cos(t), 0, 0))
        poser(rig, "front_thigh_fk.R", "XYZ", (-0.30 - 0.75 * math.sin(t), 0, 0))
        poser(rig, "front_shin_fk.R", "XYZ", (0.85 + 0.70 * math.cos(t), 0, 0))
        poser(rig, "thigh_fk.R", "XYZ", (0.50 - 0.75 * math.sin(t), 0, 0))
        poser(rig, "shin_fk.R", "XYZ", (-0.80 + 0.70 * math.cos(t), 0, 0))
        poser(rig, "thigh_fk.L", "XYZ", (0.50 + 0.75 * math.sin(t), 0, 0))
        poser(rig, "shin_fk.L", "XYZ", (-0.80 - 0.70 * math.cos(t), 0, 0))
        # corps : bob vertical net + roulis
        torse = rig.pose.bones.get("spine.002")
        if torse:
            torse.location = (0, 0, 0.035 * math.sin(2 * t))
            torse.keyframe_insert(data_path="location", frame=f)
            torse.rotation_euler = (0, 0.09 * math.sin(t), 0)
            torse.keyframe_insert(data_path="rotation_euler", frame=f)
        # tête : contre-balancement marqué
        tete = rig.pose.bones.get("head")
        if tete:
            tete.rotation_euler = (0.10 * math.sin(2 * t + 1.0), 0, 0.10 * math.sin(t))
            tete.keyframe_insert(data_path="rotation_euler", frame=f)
        # queue : vague ample le long de la chaine
        for i, nom in enumerate(("spine_fk.004", "spine_fk.005", "spine_fk.006", "spine_fk.007", "spine_fk.008")):
            pb = rig.pose.bones.get(nom)
            if pb:
                pb.rotation_euler = (0.18 * math.sin(2 * t - 0.6 * i), 0, 0.45 * math.sin(t - 0.6 * i))
                pb.keyframe_insert(data_path="rotation_euler", frame=f)
        # oreilles : twitch ponctuel
        for cote in (".L", ".R"):
            pb = rig.pose.bones.get("ear" + cote)
            if pb:
                phase = math.sin(t + (0.0 if cote == ".L" else 1.5))
                pb.rotation_euler = (0.15 * max(0.0, phase) ** 3, 0, 0)
                pb.keyframe_insert(data_path="rotation_euler", frame=f)


def animer_humain(rig, n):
    """Marche sur place : bascule FK des MEMBRES uniquement, cuisses en X,
    genoux qui plient, bras qui balancent, torse en rotation (jamais location :
    conflit avec les poids manuels head/shoulders de ce rig de test)."""
    scene.frame_set(1)
    basculer_fk(rig)
    per = 36.0
    for f in range(1, n + 1):
        scene.frame_set(f)
        t = 2 * math.pi * f / per
        # jambes : balancement X oppose, genou plie au retour
        poser(rig, "thigh_fk.L", "XYZ", (0.70 * math.sin(t), 0, 0))
        poser(rig, "shin_fk.L", "XYZ", (-0.55 + 0.45 * math.cos(t), 0, 0))
        poser(rig, "foot_fk.L", "XYZ", (0.3 - 0.25 * math.sin(t), 0, 0))
        poser(rig, "thigh_fk.R", "XYZ", (-0.70 * math.sin(t), 0, 0))
        poser(rig, "shin_fk.R", "XYZ", (-0.55 - 0.45 * math.cos(t), 0, 0))
        poser(rig, "foot_fk.R", "XYZ", (0.3 + 0.25 * math.sin(t), 0, 0))
        # bras : balancement oppose
        poser(rig, "upper_arm_fk.L", "XYZ", (0.35 * math.sin(t), 0, -1.30))
        poser(rig, "forearm_fk.L", "XYZ", (-0.25 - 0.15 * math.sin(t), 0, 0))
        poser(rig, "upper_arm_fk.R", "XYZ", (-0.35 * math.sin(t), 0, 1.30))
        poser(rig, "forearm_fk.R", "XYZ", (-0.25 + 0.15 * math.sin(t), 0, 0))
        # torse : bob vertical (poids corriges en degrade doux) + roulis
        torse = rig.pose.bones.get("torso")
        if torse:
            torse.location = (0, 0, 0.025 * abs(math.sin(t)))
            torse.keyframe_insert(data_path="location", frame=f)
            torse.rotation_euler = (0.04 * math.sin(t), 0, 0.06 * math.sin(t))
            torse.keyframe_insert(data_path="rotation_euler", frame=f)
        # tete : compensée
        tete = rig.pose.bones.get("head")
        if tete:
            tete.rotation_euler = (-0.04 * math.sin(t), 0, 0.08 * math.sin(t + 0.5))
            tete.keyframe_insert(data_path="rotation_euler", frame=f)


if anim == "loup":
    animer_loup(rig, nb_frames)
elif anim == "humain":
    animer_humain(rig, nb_frames)

# ---------------------------------------------------------------- caméra/lumière
pts = []
for o in scene.objects:
    if o.type in {"MESH", "ARMATURE"}:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
centre = Vector((sum(p.x for p in pts) / len(pts),
                 sum(p.y for p in pts) / len(pts),
                 min(p.z for p in pts) + 0.4 * (max(p.z for p in pts) - min(p.z for p in pts))))
rayon = max((p - centre).length for p in pts)
dist = rayon * 2.4 + 0.4

pivot = bpy.data.objects.new("Pivot", None)
scene.collection.objects.link(pivot)
pivot.location = centre
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
cam.parent = pivot
cam.location = (dist * 0.72, -dist * 0.72, centre.z + rayon * 0.55)
contrainte = cam.constraints.new("TRACK_TO")
cible = bpy.data.objects.new("Cible", None)
scene.collection.objects.link(cible)
cible.location = centre
contrainte.target = cible
contrainte.track_axis = "TRACK_NEGATIVE_Z"
contrainte.up_axis = "UP_Y"
scene.camera = cam

if CAM_FIXE:
    # camera fixe : 3/4 avant pour un sujet face, PROFIL pour une locomotion
    # (gallop/trot se lisent de cote, pas de face)
    pivot.rotation_euler.z = math.radians(-135 if "--profil" in argv else -38)
else:
    pivot.rotation_euler.z = math.radians(-35)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    pivot.rotation_euler.z = math.radians(325)
    pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=nb_frames)


def area_light(nom, energie, taille, loc):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie
    ld.size = taille
    lo = bpy.data.objects.new(nom, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    contr = lo.constraints.new("TRACK_TO")
    contr.target = cible
    contr.track_axis = "TRACK_NEGATIVE_Z"
    contr.up_axis = "UP_Y"


area_light("Key", 220 * rayon ** 2, 1.2, (centre.x + 2 * rayon, centre.y - 2.5 * rayon, centre.z + 3 * rayon))
area_light("Fill", 70 * rayon ** 2, 2.0, (centre.x - 3 * rayon, centre.y - 1.5 * rayon, centre.z + 1.5 * rayon))
area_light("Rim", 130 * rayon ** 2, 1.0, (centre.x, centre.y + 3 * rayon, centre.z + 2.5 * rayon))
monde = scene.world or bpy.data.worlds.new("Monde")
scene.world = monde
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.87, 0.9, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 0.55

# sol receveur d'ombre
bpy.ops.mesh.primitive_plane_add(size=rayon * 12, location=(centre.x, centre.y, 0))
sol = bpy.context.active_object
mat = bpy.data.materials.new("Sol")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.55, 0.57, 0.6, 1.0)
bsdf.inputs["Roughness"].default_value = 0.9
sol.data.materials.append(mat)

# ---------------------------------------------------------------- rendu
scene.render.engine = "BLENDER_EEVEE"  # 5.2 : EEVEE Next est le défaut, l'enum a perdu son suffixe
scene.eevee.taa_render_samples = 32
scene.render.resolution_x = res
scene.render.resolution_y = int(res * 9 / 16)
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = nb_frames

dossier_png = mp4_out.replace(".mp4", "_png")
os.makedirs(dossier_png, exist_ok=True)
scene.render.image_settings.file_format = "PNG"
for f in range(1, nb_frames + 1):
    if BOUCLE:
        scene.frame_set(action_debut + ((f - 1) % (action_fin - action_debut + 1)))
    else:
        scene.frame_set(f)
    scene.render.filepath = os.path.join(dossier_png, "frame_%04d.png" % f)
    bpy.ops.render.render(write_still=True)
    if f % 12 == 0 or f == nb_frames:
        print("RENDU %d/%d" % (f, nb_frames))

ffmpeg = trouver_ffmpeg()
cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", os.path.join(dossier_png, "frame_%04d.png"),
       "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", mp4_out]
subprocess.run(cmd, check=True, capture_output=True)
print("CLIP_PRET:" + mp4_out)
