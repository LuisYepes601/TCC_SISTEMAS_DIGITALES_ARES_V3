"""ui/styles/performance_palette.py"""
from dataclasses import dataclass
from ui.styles.theme import THEME_DARK, THEME_LIGHT

COLOR_CPU="#22d3ee"; COLOR_MEM="#38bdf8"; COLOR_DISK="#4ade80"; COLOR_WIFI="#e879f9"; COLOR_GPU="#a78bfa"

@dataclass(frozen=True)
class PerformancePalette:
    bg: str; bg_elevated: str; bg_card: str; text_primary: str; text_secondary: str
    card_border: str; card_hover: str; card_selected: str; grid_alpha: float
    axis_color: str; fill_cpu: str; fill_mem: str; fill_disk: str; fill_wifi: str; fill_gpu: str

PALETTE_DARK = PerformancePalette(
    bg="#020617", bg_elevated="#020817", bg_card="#020617",
    text_primary="#e5e7eb", text_secondary="#9ca3af",
    card_border="rgba(148,163,184,0.35)", card_hover="rgba(15,23,42,0.95)", card_selected="rgba(15,23,42,1)",
    grid_alpha=0.10, axis_color="#4b5563",
    fill_cpu="#9bd7fcec", fill_mem="#3338bdf8", fill_disk="#334ade80", fill_wifi="#33e879f9", fill_gpu="#33a78bfa",
)
PALETTE_LIGHT = PerformancePalette(
    bg="#e8ecf0", bg_elevated="#ffffff", bg_card="#f1f5f9",
    text_primary="#0f172a", text_secondary="#64748b",
    card_border="rgba(15,23,42,0.12)", card_hover="rgba(226,232,240,0.95)", card_selected="#ffffff",
    grid_alpha=0.18, axis_color="#94a3b8",
    fill_cpu="#9bd7fcec", fill_mem="#5538bdf8", fill_disk="#554ade80", fill_wifi="#55e879f9", fill_gpu="#55a78bfa",
)
def palette_for_theme(theme): return PALETTE_LIGHT if theme == THEME_LIGHT else PALETTE_DARK
