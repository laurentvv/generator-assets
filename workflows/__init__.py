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
    "Mesh3DWorkflow"
]
