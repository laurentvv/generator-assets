"""
Module d'enregistrement des workflows 2D & 3D.
"""

from workflows.base import BaseWorkflow, WorkflowRegistry
from workflows.generate import GenerateWorkflow
from workflows.upscale import UpscaleWorkflow
from workflows.spritesheet import SpriteSheetWorkflow
from workflows.variations import VariationsWorkflow
from workflows.tileable import TileableWorkflow
from workflows.pixelart import PixelArtWorkflow
from workflows.batch import BatchWorkflow
from workflows.material3d import Material3DWorkflow
from workflows.skybox import SkyboxWorkflow
from workflows.turnaround3d import Turnaround3DWorkflow
from workflows.mesh3d import Mesh3DWorkflow
from workflows.rembg import RembgWorkflow
from workflows.flowmap import FlowmapWorkflow
from workflows.ui_9slice import UI9SliceWorkflow
from workflows.voxel3d import Voxel3DWorkflow
from workflows.autotile_pack import AutotilePackWorkflow
from workflows.rife_interp import RifeInterpWorkflow
from workflows.vfx_flipbook import VFXFlipbookWorkflow
from workflows.rpg_portrait import RPGPortraitWorkflow
from workflows.sfx import SFXWorkflow
from workflows.ip_adapter import IPAdapterWorkflow
from workflows.anim_loop import AnimLoopWorkflow
from workflows.pose_control import PoseControlWorkflow
from workflows.tts_dialogue import TTSDialogueWorkflow
from workflows.audio_ambience import AudioAmbienceWorkflow
from workflows.music_bg import MusicBgWorkflow
from workflows.outfit import OutfitWorkflow
from workflows.video import VideoWorkflow

__all__ = [
    "BaseWorkflow",
    "WorkflowRegistry",
    "GenerateWorkflow",
    "UpscaleWorkflow",
    "SpriteSheetWorkflow",
    "VariationsWorkflow",
    "TileableWorkflow",
    "PixelArtWorkflow",
    "BatchWorkflow",
    "Material3DWorkflow",
    "SkyboxWorkflow",
    "Turnaround3DWorkflow",
    "Mesh3DWorkflow",
    "RembgWorkflow",
    "FlowmapWorkflow",
    "UI9SliceWorkflow",
    "Voxel3DWorkflow",
    "AutotilePackWorkflow",
    "RifeInterpWorkflow",
    "VFXFlipbookWorkflow",
    "RPGPortraitWorkflow",
    "SFXWorkflow",
    "IPAdapterWorkflow",
    "AnimLoopWorkflow",
    "PoseControlWorkflow",
    "TTSDialogueWorkflow",
    "AudioAmbienceWorkflow",
    "MusicBgWorkflow",
    "OutfitWorkflow",
    "VideoWorkflow"
]


