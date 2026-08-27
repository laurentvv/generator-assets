# -*- coding: utf-8 -*-
"""
Workflow Outfit : Génération 100% automatisée de tenues PBR pour personnages MakeHuman / Godot 4.
Génère des textures PBR sans raccord (Albedo + Normal + Roughness) par IA locale (Flux.1 / SDXL)
et les applique directement sur les vêtements 3D du personnage dans Blender sans aucune action manuelle.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import generer_normal_map, generer_roughness_map
from core.llm import construire_prompt_coherant
from core.blender_ops import trouver_blender
from workflows.base import BaseWorkflow, WorkflowRegistry

@WorkflowRegistry.register
class OutfitWorkflow(BaseWorkflow):
    name = "outfit"
    description = "Génération 100% automatique de tenues PBR (tissus/cuirs) pour personnages 3D"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        char_name = params.get("character", "marc_novice")
        top_prompt = params.get("top", "rustic medieval beige burlap tunic fabric")
        shoes_prompt = params.get("shoes", "worn dark brown medieval leather shoes texture")
        blend_file = params.get("blend") or os.path.join(DEFAULT_OUTPUT_DIR, f"{char_name}.blend")
        glb_file = os.path.join(DEFAULT_OUTPUT_DIR, f"{char_name}.glb")
        render_file = os.path.join(DEFAULT_OUTPUT_DIR, f"{char_name}_beauty_render.png")
        
        text_dir = os.path.join(DEFAULT_OUTPUT_DIR, "textures", char_name)
        os.makedirs(text_dir, exist_ok=True)
        
        self.log(f"🚀 Génération automatique de la tenue PBR pour '{char_name}'...")
        
        # 1. Génération Albedo + Normal + Roughness pour le Torse / Tunique
        self.log(f"🎨 [1/3] Génération du tissu pour le haut : '{top_prompt}'...")
        top_slug = slugifier_texte(top_prompt)[:20]
        top_albedo_path = os.path.join(text_dir, f"top_{top_slug}_albedo.png")
        top_norm_path = os.path.join(text_dir, f"top_{top_slug}_normal.png")
        
        if not os.path.exists(top_albedo_path):
            prompt_top = construire_prompt_coherant(
                concept=top_prompt,
                type_asset="tile",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor="seamless texture, macro fabric weave pattern, top-down flat lighting, clean repeatable cloth texture, photorealistic",
                custom_cadrage="seamless repeatable tile texture"
            )
            img_top = generer_image_vulkan(
                prompt=prompt_top,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                width=1024,
                height=1024,
                steps=20,
                circular=True
            )
            img_top.save(top_albedo_path, "PNG")
            norm_top = generer_normal_map(img_top, strength=3.0)
            norm_top.save(top_norm_path, "PNG")
        
        # 2. Génération Albedo + Normal pour les Chaussures
        self.log(f"👢 [2/3] Génération de la matière pour les chaussures : '{shoes_prompt}'...")
        shoes_slug = slugifier_texte(shoes_prompt)[:20]
        shoes_albedo_path = os.path.join(text_dir, f"shoes_{shoes_slug}_albedo.png")
        shoes_norm_path = os.path.join(text_dir, f"shoes_{shoes_slug}_normal.png")
        
        if not os.path.exists(shoes_albedo_path):
            prompt_shoes = construire_prompt_coherant(
                concept=shoes_prompt,
                type_asset="tile",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor="seamless texture, rough worn brown leather texture, top-down flat lighting, clean repeatable surface, photorealistic",
                custom_cadrage="seamless repeatable tile texture"
            )
            img_shoes = generer_image_vulkan(
                prompt=prompt_shoes,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                width=1024,
                height=1024,
                steps=20,
                circular=True
            )
            img_shoes.save(shoes_albedo_path, "PNG")
            norm_shoes = generer_normal_map(img_shoes, strength=3.0)
            norm_shoes.save(shoes_norm_path, "PNG")
        
        # 3. Application 100% automatique dans Blender
        self.log(f"🔨 [3/3] Application des shaders PBR dans Blender...")
        blender_bin = trouver_blender()
        if not blender_bin:
            raise RuntimeError("Exécutable Blender introuvable.")

        script_blender = f"""# -*- coding: utf-8 -*-
import bpy, os

blend_file = r"{os.path.abspath(blend_file)}"
if os.path.exists(blend_file):
    bpy.ops.wm.open_mainfile(filepath=blend_file)

def apply_pbr_material(obj_part_name, albedo_file, normal_file, uv_scale, roughness_val):
    obj = next((o for o in bpy.data.objects if obj_part_name.lower() in o.name.lower()), None)
    if not obj:
        print(f"⚠️ Objet {{obj_part_name}} non trouvé dans la scène.")
        return
    
    mat_name = f"PBR_{{obj.name}}"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    out_node = nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (400, 0)
    
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    bsdf.inputs['Roughness'].default_value = roughness_val
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    
    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-700, 0)
    
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-500, 0)
    mapping.inputs['Scale'].default_value = (uv_scale, uv_scale, uv_scale)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
    
    if os.path.exists(albedo_file):
        tex_alb = nodes.new('ShaderNodeTexImage')
        tex_alb.location = (-250, 100)
        tex_alb.image = bpy.data.images.load(albedo_file)
        links.new(mapping.outputs['Vector'], tex_alb.inputs['Vector'])
        links.new(tex_alb.outputs['Color'], bsdf.inputs['Base Color'])
        
    if os.path.exists(normal_file):
        tex_n = nodes.new('ShaderNodeTexImage')
        tex_n.location = (-250, -200)
        tex_n.image = bpy.data.images.load(normal_file)
        tex_n.image.colorspace_settings.name = 'Non-Color'
        links.new(mapping.outputs['Vector'], tex_n.inputs['Vector'])
        
        norm_node = nodes.new('ShaderNodeNormalMap')
        norm_node.location = (-50, -200)
        links.new(tex_n.outputs['Color'], norm_node.inputs['Color'])
        links.new(norm_node.outputs['Normal'], bsdf.inputs['Normal'])
        
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    print(f"✅ Matériau PBR appliqué sur {{obj.name}}")

apply_pbr_material("worksuit", r"{os.path.abspath(top_albedo_path)}", r"{os.path.abspath(top_norm_path)}", 4.0, 0.85)
apply_pbr_material("shoes", r"{os.path.abspath(shoes_albedo_path)}", r"{os.path.abspath(shoes_norm_path)}", 3.0, 0.70)

bpy.ops.wm.save_as_mainfile(filepath=blend_file)
print(f"💾 Scène Blender sauvegardée : {{blend_file}}")

# Export GLB pour Godot
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=r"{os.path.abspath(glb_file)}",
    export_format='GLB',
    use_selection=True,
    export_apply=True,
    export_materials='EXPORT',
    export_yup=True
)
print(f"🎮 GLB Godot exporté : {glb_file}")
"""
        res = subprocess.run([blender_bin, "--background", "--python-expr", script_blender], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.log(res.stdout)
        
        # 4. Rendu de validation Cycles
        from scripts.character_pipeline import etape_3_rendre_validation
        etape_3_rendre_validation(blender_bin, glb_file, render_file)
        
        self.log(f"🎉 Tenue générée et appliquée avec succès pour '{char_name}' !")
        return {
            "blend": blend_file,
            "glb": glb_file,
            "render": render_file,
            "top_albedo": top_albedo_path,
            "shoes_albedo": shoes_albedo_path
        }
