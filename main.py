#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"
Split-screen Game Menu Design & Character Concept Art
Arcade-stijl mini-games prototype in Pygame.

- Menu met 2 opties: PRECISION CUT en STREET BRAWL
- Game 1: Precision Cut (First-person knipgame)
- Game 2: Street Brawl (2D fighter snapshot/mini)
- High score board (top 10), naam invoeren indien in lijst

Besturing:
- Menu: Pijltjes links/rechts of A/D, Enter om te starten, Esc om af te sluiten
- Game 1 (Precision Cut):
  - Muis bewegen = tondeuse bewegen
  - Linker muisknop (of spatie) = knippen
  - Doel: Hou de tondeuse in de Sweet Zone, bouw PRECISION op, maak combo's met vloeiende beweging
- Game 2 (Street Brawl):
  - Tank (Speler) besturing: A/D=L/R, W=Sprong, J=Punch, K=Super (als meter vol)
  - Technicus (AI) ontwijkt en beweegt terug bij gevaar
  - Doel: Breng de health van de tegenstander omlaag binnen 99 seconden
- Na game einde: als score top 10, voer naam in; daarna High Score Board

Benodigd: Python 3.10+ en pygame 2.5+
""
from __future__ import annotations

import json
import math
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

try:
    import pygame
    from pygame import Surface, Rect
    import pygame.freetype as freetype
except Exception as e:
    print("Pygame is vereist. Installeer met: pip install pygame", file=sys.stderr)
    raise

# ------------------------------------------------------------
# Config en Constants
# ------------------------------------------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 60
ASPECT = WIDTH / HEIGHT
DATA_DIR = Path(os.getcwd())
HS_FILE = DATA_DIR / "highscores.json"

# Kleuren (allemaal tuples met ints 0..255 om ValueError te vermijden)
COLORS = {
    "BLACK": (10, 10, 12),
    "NEAR_BLACK": (18, 18, 22),
    "WOOD_BROWN": (80, 55, 35),
    "WOOD_LIGHT": (120, 85, 55),
    "NEON_RED": (255, 36, 64),
    "NEON_RED_SOFT": (255, 80, 100),
    "ELECTRIC_BLUE": (20, 200, 255),
    "ELECTRIC_BLUE_SOFT": (90, 220, 255),
    "GOLD": (245, 200, 80),
    "GOLD_DARK": (180, 140, 50),
    "WHITE": (240, 240, 240),
    "GREY": (120, 120, 120),
    "GREEN": (40, 200, 120),
    "YELLOW": (255, 220, 60),
    "ORANGE": (255, 140, 50),
    "RED": (220, 40, 40),
}

# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def draw_outline(surface: Surface, draw_func: Callable[[Surface], None], thickness: int = 6, color: Tuple[int, int, int] = COLORS["BLACK"], fill_first: bool = True):
    temp = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    # draw fill on temp
    draw_func(temp)
    # create outline by expanding alpha
    alpha = pygame.surfarray.pixels_alpha(temp).copy()
    del alpha
    # Blit multiple offsets to simulate outline
    outline = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx * dx + dy * dy <= thickness * thickness:
                outline.blit(temp, (dx, dy))
    # Tint outline to black
    arr = pygame.surfarray.pixels3d(outline)
    arr[:, :, 0] = color[0]
    arr[:, :, 1] = color[1]
    arr[:, :, 2] = color[2]
    del arr
    surface.blit(outline, (0, 0))
    if fill_first:
        surface.blit(temp, (0, 0))


def draw_neon_text(dst: Surface, text: str, font: freetype.Font, pos: Tuple[int, int], color: Tuple[int, int, int] = COLORS["NEON_RED" ], glow_color: Tuple[int, int, int] = COLORS["NEON_RED_SOFT" ], center: bool = False, scale: float = 1.0):
    # Render crisp text
    surf, rect = font.render(text, fgcolor=color)
    if scale != 1.0:
        surf = pygame.transform.smoothscale(surf, (int(surf.get_width() * scale), int(surf.get_height() * scale)))
        rect = surf.get_rect()
    x, y = pos
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    # Glow passes
    glow = pygame.Surface((rect.width + 60, rect.height + 40), pygame.SRCALPHA)
    for r in range(6, 28, 4):
        alpha = int(60 * (1.0 - (r - 6) / 22.0))
        if alpha < 5:
            alpha = 5
        glow_surf, _ = font.render(text, fgcolor=(glow_color[0], glow_color[1], glow_color[2]))
        glow_surf = pygame.transform.smoothscale(glow_surf, (int(glow_surf.get_width() * (1 + r / 40.0)), int(glow_surf.get_height() * (1 + r / 40.0))))
        gs_rect = glow_surf.get_rect(center=(glow.get_width() // 2, glow.get_height() // 2))
        temp = pygame.Surface(glow.get_size(), pygame.SRCALPHA)
        temp.blit(glow_surf, gs_rect)
        temp.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        glow.blit(temp, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
    dst.blit(glow, (rect.x - 30, rect.y - 20), special_flags=pygame.BLEND_PREMULTIPLIED)
    dst.blit(surf, rect)


def load_font(size: int = 36) -> freetype.Font:
    try:
        return freetype.SysFont("ArcadeClassic, PressStart2P, Impact, Arial Black, Arial, DejaVu Sans", size)
    except Exception:
        return freetype.SysFont(None, size)

# ------------------------------------------------------------
# Achtergrond en Iconen tekenen
# ------------------------------------------------------------

def draw_barbershop_bg(dst: Surface):
    # Donkere, industriële barbershop met houten vloer en neon sign
    dst.fill(COLORS["NEAR_BLACK"])  # muren
    # Industriële pijpen
    for i in range(6):
        x = 100 + i * 200
        pygame.draw.rect(dst, (30, 30, 35), Rect(x, 60, 20, 280))
        pygame.draw.rect(dst, (45, 45, 55), Rect(x + 3, 60, 2, 280))
    # Houten vloer
    floor_h = HEIGHT // 3
    pygame.draw.rect(dst, COLORS["WOOD_BROWN"], Rect(0, HEIGHT - floor_h, WIDTH, floor_h))
    # Planken
    for i in range(0, WIDTH, 40):
        col = COLORS["WOOD_LIGHT"] if (i // 40) % 2 == 0 else COLORS["WOOD_BROWN"]
        pygame.draw.rect(dst, col, Rect(i, HEIGHT - floor_h + 4, 36, floor_h - 8))
    # Spiegels (wazig)
    for i in range(3):
        w = 260
        h = 160
        x = 120 + i * 360
        y = 120
        r = Rect(x, y, w, h)
        pygame.draw.rect(dst, (40, 45, 50), r, border_radius=10)
        pygame.draw.rect(dst, (70, 75, 85), Rect(r.x + 10, r.y + 10, r.w - 20, r.h - 20), border_radius=8)
        # highlight
        pygame.draw.rect(dst, (90, 100, 115), Rect(r.x + 20, r.y + 20, r.w - 40, r.h - 40), border_radius=6)
    # Neon-sign
    font = load_font(42)
    draw_neon_text(dst, "IT'S A CUT-THROAT BUSINESS", font, (WIDTH // 2, 60), COLORS["NEON_RED"], COLORS["NEON_RED_SOFT"], center=True, scale=1.0)


def draw_vintage_chair(dst: Surface, pos: Tuple[int, int], scale: float = 1.0):
    x, y = pos
    w, h = int(160 * scale), int(220 * scale)
    r = Rect(x - w // 2, y - h // 2, w, h)
    # Body
    pygame.draw.rect(dst, (90, 0, 0), Rect(r.x + 20, r.y + 30, r.w - 40, r.h - 100), border_radius=12)
    pygame.draw.rect(dst, COLORS["BLACK"], Rect(r.x + 20, r.y + 30, r.w - 40, r.h - 100), width=6, border_radius=12)
    # Rugleuning
    pygame.draw.rect(dst, (100, 0, 0), Rect(r.x + 30, r.y + 10, r.w - 60, 50), border_radius=10)
    pygame.draw.rect(dst, COLORS["BLACK"], Rect(r.x + 30, r.y + 10, r.w - 60, 50), width=6, border_radius=10)
    # Zitting
    pygame.draw.rect(dst, (110, 5, 5), Rect(r.x + 30, r.y + 100, r.w - 60, 50), border_radius=8)
    pygame.draw.rect(dst, COLORS["BLACK"], Rect(r.x + 30, r.y + 100, r.w - 60, 50), width=6, border_radius=8)
    # Voet
    pygame.draw.rect(dst, (60, 60, 60), Rect(r.centerx - 10, r.bottom - 50, 20, 40))
    pygame.draw.rect(dst, COLORS["BLACK"], Rect(r.centerx - 10, r.bottom - 50, 20, 40), width=6)
    pygame.draw.rect(dst, (60, 60, 60), Rect(r.centerx - 50, r.bottom - 20, 100, 12), border_radius=6)
    pygame.draw.rect(dst, COLORS["BLACK"], Rect(r.centerx - 50, r.bottom - 20, 100, 12), width=6, border_radius=6)


def draw_scissors(dst: Surface, center: Tuple[int, int], scale: float = 1.0, color: Tuple[int, int, int] = COLORS["GOLD"]):
    cx, cy = center
    blade_len = int(70 * scale)
    handle_r = int(12 * scale)
    # Blades
    pygame.draw.line(dst, color, (cx, cy), (cx - blade_len, cy - 20), 6)
    pygame.draw.line(dst, color, (cx, cy), (cx + blade_len, cy + 20), 6)
    # Handles
    pygame.draw.circle(dst, color, (cx - 24, cy + 24), handle_r, width=6)
    pygame.draw.circle(dst, color, (cx + 24, cy - 24), handle_r, width=6)


def draw_clippers(dst: Surface, center: Tuple[int, int], scale: float = 1.0, body_color: Tuple[int, int, int] = COLORS["GOLD" ]):
    cx, cy = center
    w = int(40 * scale)
    h = int(80 * scale)
    body = Rect(cx - w // 2, cy - h // 2, w, h)
    pygame.draw.rect(dst, body_color, body, border_radius=8)
    pygame.draw.rect(dst, COLORS["GOLD_DARK"], body, width=6, border_radius=8)
    # Blades
    pygame.draw.rect(dst, COLORS["WHITE"], Rect(body.x + 6, body.y - 8, body.w - 12, 16), border_radius=4)
    pygame.draw.rect(dst, COLORS["BLACK"], Rect(body.x + 6, body.y - 8, body.w - 12, 16), width=4, border_radius=4)


def draw_flaming_fist(dst: Surface, center: Tuple[int, int], scale: float = 1.0):
    cx, cy = center
    fist_r = int(26 * scale)
    # Flames (electric blue + neon red accents)
    for i in range(6):
        angle = i * math.pi / 3
        rx = cx + int(math.cos(angle) * (fist_r + 12))
        ry = cy + int(math.sin(angle) * (fist_r + 12))
        col = COLORS["ELECTRIC_BLUE_SOFT"] if i % 2 == 0 else COLORS["NEON_RED_SOFT"]
        pygame.draw.circle(dst, col, (rx, ry), int(12 * scale))
    # Fist
    pygame.draw.circle(dst, COLORS["ORANGE"], (cx, cy), fist_r)
    pygame.draw.circle(dst, COLORS["BLACK"], (cx, cy), fist_r, width=6)
    # Knuckles lines
    for i in range(-1, 2):
        pygame.draw.line(dst, COLORS["BLACK"], (cx - fist_r + 8, cy + i * 8), (cx + fist_r - 8, cy + i * 8), 4)

# ------------------------------------------------------------
# Character schetsen (cartoony, dikke outlines)
# ------------------------------------------------------------

def draw_character(dst: Surface, pos: Tuple[int, int], scale: float, palette: Tuple[int, int, int], archetype: str):
    # Eenvoudige cartoon-figuur met dikke omlijning, pose afhankelijk van archetype
    x, y = pos
    body_color = palette
    # Schaduw
    pygame.draw.ellipse(dst, (0, 0, 0, 80), Rect(x - int(50 * scale), y + int(40 * scale), int(100 * scale), int(20 * scale)))
    # Torso
    torso = Rect(x - int(40 * scale), y - int(60 * scale), int(80 * scale), int(100 * scale))
    pygame.draw.rect(dst, body_color, torso, border_radius=12)
    pygame.draw.rect(dst, COLORS["BLACK"], torso, width=6, border_radius=12)
    # Head
    pygame.draw.circle(dst, (240, 200, 160), (x, y - int(90 * scale)), int(28 * scale))
    pygame.draw.circle(dst, COLORS["BLACK"], (x, y - int(90 * scale)), int(28 * scale), width=6)
    # Facial features
    pygame.draw.line(dst, COLORS["BLACK"], (x - int(8 * scale), y - int(95 * scale)), (x - int(2 * scale), y - int(92 * scale)), 3)
    pygame.draw.line(dst, COLORS["BLACK"], (x + int(2 * scale), y - int(92 * scale)), (x + int(8 * scale), y - int(95 * scale)), 3)
    pygame.draw.line(dst, COLORS["BLACK"], (x - int(10 * scale), y - int(80 * scale)), (x + int(10 * scale), y - int(80 * scale)), 4)

    # Arms/pose by archetype
    if archetype == "tank":
        # Arms crossed
        pygame.draw.line(dst, COLORS["BLACK"], (x - int(36 * scale), y - int(10 * scale)), (x + int(36 * scale), y + int(10 * scale)), 10)
        pygame.draw.line(dst, COLORS["BLACK"], (x + int(36 * scale), y - int(10 * scale)), (x - int(36 * scale), y + int(10 * scale)), 10)
        # Beard
        pygame.draw.arc(dst, COLORS["BLACK"], Rect(x - int(26 * scale), y - int(98 * scale), int(52 * scale), int(36 * scale)), math.pi * 0.1, math.pi - 0.1, 6)
        # Tattoos (simple lines)
        for i in range(4):
            pygame.draw.line(dst, COLORS["BLACK"], (x - int(30 * scale) + i * int(12 * scale), y + int(6 * scale)), (x - int(20 * scale) + i * int(12 * scale), y + int(20 * scale)), 3)
    elif archetype == "allround":
        # Classic stance
        pygame.draw.line(dst, COLORS["BLACK"], (x - int(50 * scale), y), (x - int(10 * scale), y - int(20 * scale)), 8)
        pygame.draw.line(dst, COLORS["BLACK"], (x + int(10 * scale), y - int(20 * scale)), (x + int(50 * scale), y), 8)
        # Hair (fade)
        pygame.draw.arc(dst, COLORS["BLACK"], Rect(x - int(28 * scale), y - int(105 * scale), int(56 * scale), int(30 * scale)), math.pi, 2 * math.pi, 6)
    elif archetype == "brawler":
        # Lean forward fists up
        pygame.draw.line(dst, COLORS["BLACK"], (x - int(44 * scale), y + int(10 * scale)), (x - int(10 * scale), y - int(10 * scale)), 10)
        pygame.draw.line(dst, COLORS["BLACK"], (x + int(10 * scale), y - int(10 * scale)), (x + int(44 * scale), y + int(10 * scale)), 10)
        pygame.draw.circle(dst, COLORS["BLACK"], (x - int(56 * scale), y + int(10 * scale)), int(10 * scale))
        pygame.draw.circle(dst, COLORS["BLACK"], (x + int(56 * scale), y + int(10 * scale)), int(10 * scale))
    else:  # technicus
        # Agile pose, one arm with scissors
        pygame.draw.line(dst, COLORS["BLACK"], (x - int(40 * scale), y - int(30 * scale)), (x - int(5 * scale), y - int(10 * scale)), 8)
        pygame.draw.line(dst, COLORS["BLACK"], (x + int(5 * scale), y - int(10 * scale)), (x + int(46 * scale), y - int(40 * scale)), 8)
        # Scissors in hand
        draw_scissors(dst, (x + int(54 * scale), y - int(44 * scale)), scale=0.8, color=COLORS["GOLD"])
        # Glasses+mustache
        pygame.draw.rect(dst, COLORS["BLACK"], Rect(x - int(18 * scale), y - int(98 * scale), int(36 * scale), int(8 * scale)))
        pygame.draw.line(dst, COLORS["BLACK"], (x - int(10 * scale), y - int(82 * scale)), (x + int(10 * scale), y - int(82 * scale)), 4)

# ------------------------------------------------------------
# Particles (vonken/schuim etc.)
# ------------------------------------------------------------
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: Tuple[int, int, int]
    size: float
    gravity: float = 0.0

    def update(self, dt: float):
        self.life -= dt
        self.vx *= 0.98
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, dst: Surface):
        if self.life > 0.0:
            alpha = int(255 * clamp(self.life, 0.0, 1.0))
            s = max(1, int(self.size))
            surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (self.color[0], self.color[1], self.color[2], alpha), (s, s), s)
            dst.blit(surf, (int(self.x - s), int(self.y - s)))

# ------------------------------------------------------------
# High Scores opslag
# ------------------------------------------------------------
DEFAULT_HS = {
    "precision": [],
    "brawl": [],
}


def load_highscores() -> dict:
    if HS_FILE.exists():
        try:
            with open(HS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # validate structure
                for key in DEFAULT_HS.keys():
                    if key not in data or not isinstance(data[key], list):
                        data[key] = []
                return data
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_HS))


def save_highscores(data: dict):
    try:
        with open(HS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Kon highscores niet opslaan:", e)

# ------------------------------------------------------------
# Scene management
# ------------------------------------------------------------
class Scene:
    def __init__(self, app: "GameApp"):
        self.app = app

    def handle_event(self, e: pygame.event.Event):
        pass

    def update(self, dt: float):
        pass

    def draw(self, dst: Surface):
        pass


class GameApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Cut-Throat: Arcade Edition")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.scenes: List[Scene] = []
        self.running = True
        self.font_small = load_font(24)
        self.font = load_font(36)
        self.font_big = load_font(64)
        self.highscores = load_highscores()
        self.push(MenuScene(self))

    def push(self, scene: Scene):
        self.scenes.append(scene)

    def pop(self):
        if self.scenes:
            self.scenes.pop()

    def replace(self, scene: Scene):
        if self.scenes:
            self.scenes[-1] = scene
        else:
            self.scenes.append(scene)

    def current(self) -> Scene:
        return self.scenes[-1]

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                else:
                    self.current().handle_event(e)
            self.current().update(dt)
            self.current().draw(self.screen)
            pygame.display.flip()
        save_highscores(self.highscores)
        pygame.quit()

# ------------------------------------------------------------
# Menu Scene
# ------------------------------------------------------------
class MenuScene(Scene):
    def __init__(self, app: GameApp):
        super().__init__(app)
        self.select = 0  # 0 = left (Precision Cut), 1 = right (Street Brawl)
        self.pulse = 0.0

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_LEFT, pygame.K_a):
                self.select = 0
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                self.select = 1
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.select == 0:
                    self.app.push(PrecisionCutGame(self.app))
                else:
                    self.app.push(StreetBrawlGame(self.app))
            elif e.key == pygame.K_ESCAPE:
                self.app.running = False
        elif e.type == pygame.MOUSEBUTTONDOWN:
            mx, my = e.pos
            if mx < WIDTH // 2:
                self.select = 0
                self.app.push(PrecisionCutGame(self.app))
            else:
                self.select = 1
                self.app.push(StreetBrawlGame(self.app))

    def update(self, dt: float):
        self.pulse += dt

    def draw(self, dst: Surface):
        draw_barbershop_bg(dst)
        # Split overlay
        left = Rect(0, 0, WIDTH // 2, HEIGHT)
        right = Rect(WIDTH // 2, 0, WIDTH // 2, HEIGHT)
        # Tint
        left_tint = pygame.Surface(left.size, pygame.SRCALPHA)
        right_tint = pygame.Surface(right.size, pygame.SRCALPHA)
        left_tint.fill((20, 20, 25, 160))
        right_tint.fill((20, 20, 25, 160))
        dst.blit(left_tint, left)
        dst.blit(right_tint, right)

        # LEFT: PRECISION CUT
        draw_vintage_chair(dst, (WIDTH // 4, HEIGHT // 2 + 50), scale=1.1)
        draw_scissors(dst, (WIDTH // 4 - 90, HEIGHT // 2 - 90), scale=1.2)
        draw_clippers(dst, (WIDTH // 4 + 60, HEIGHT // 2 - 80), scale=1.2)
        draw_neon_text(dst, "PRECISION CUT", self.app.font, (WIDTH // 4, 120), COLORS["ELECTRIC_BLUE"], COLORS["ELECTRIC_BLUE_SOFT"], center=True, scale=1.1)

        # RIGHT: STREET BRAWL
        draw_neon_text(dst, "STREET BRAWL", self.app.font, (WIDTH * 3 // 4, 120), COLORS["NEON_RED"], COLORS["NEON_RED_SOFT"], center=True, scale=1.1)
        # Icon flaming fist
        draw_flaming_fist(dst, (WIDTH * 3 // 4, 170), scale=1.6)
        # 4 medewerkers lineup (silhouetten met accent)
        palette = [ (120, 40, 40), (40, 120, 180), (150, 110, 50), (80, 60, 140) ]
        names = ["tank", "allround", "brawler", "technicus"]
        for i, name in enumerate(names):
            px = WIDTH // 2 + 120 + i * 110
            py = HEIGHT // 2 + 70
            draw_character(dst, (px, py), 0.9, palette[i], name)

        # Focus highlight op selectie
        glow_alpha = int(120 + 80 * (0.5 + 0.5 * math.sin(self.pulse * 3)))
        sel_rect = left if self.select == 0 else right
        sel_surf = pygame.Surface(sel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(sel_surf, (255, 255, 255, glow_alpha), sel_surf.get_rect(), width=10)
        dst.blit(sel_surf, sel_rect)

        # Footer hints
        hint = "Gebruik Links/Rechts of A/D om te kiezen. Enter om te starten. Esc om te stoppen."
        surf, r = self.app.font_small.render(hint, COLORS["WHITE"])
        dst.blit(surf, (WIDTH // 2 - r.width // 2, HEIGHT - 40))

# ------------------------------------------------------------
# Game 1: Precision Cut
# ------------------------------------------------------------
class PrecisionCutGame(Scene):
    def __init__(self, app: GameApp):
        super().__init__(app)
        self.time_limit = 40.0
        self.time_left = self.time_limit
        self.precision_score = 0.0
        self.combo = 0
        self.combo_timer = 0.0
        self.sparks: List[Particle] = []
        self.mouse_pos = (WIDTH // 2, HEIGHT // 2)
        self.cutting = False
        # Sweet zone band (waar knippen meest precies telt)
        self.sweet_y0 = HEIGHT // 2 - 80
        self.sweet_y1 = HEIGHT // 2 + 60
        # Precision meter waarde 0..1
        self.precision_meter = 0.0
        # Floating text effect
        self.perfect_alpha = 0.0

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.pop()
            elif e.key == pygame.K_SPACE:
                self.cutting = True
        elif e.type == pygame.KEYUP:
            if e.key == pygame.K_SPACE:
                self.cutting = False
        elif e.type == pygame.MOUSEMOTION:
            self.mouse_pos = e.pos
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.cutting = True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.cutting = False

    def update(self, dt: float):
        self.time_left -= dt
        if self.time_left <= 0:
            self.finish_game()
            return
        mx, my = self.mouse_pos
        # Bepaal of we in de sweet zone zitten
        in_zone = self.sweet_y0 <= my <= self.sweet_y1
        # Simuleer steady hand door horizontale jitter straf te geven
        jitter = abs(pygame.mouse.get_rel()[0]) + abs(pygame.mouse.get_rel()[1])
        steady = jitter < 4
        if self.cutting:
            # Vonken en combo effect
            for _ in range(3):
                ang = random.random() * 2 * math.pi
                spd = 120 + random.random() * 200
                col = COLORS["ELECTRIC_BLUE"] if random.random() < 0.7 else COLORS["WHITE"]
                self.sparks.append(Particle(mx, my, math.cos(ang) * spd, math.sin(ang) * spd, 0.4 + random.random() * 0.4, col, size=2 + random.random() * 3))
            if in_zone and steady:
                self.precision_meter = clamp(self.precision_meter + 0.8 * dt, 0.0, 1.0)
                self.combo += 1
                self.combo_timer = 1.0
                self.precision_score += 5.0 * dt * (1.0 + self.combo * 0.02)
                if self.precision_meter > 0.95:
                    self.perfect_alpha = 1.0
            else:
                self.precision_meter = clamp(self.precision_meter - 0.6 * dt, 0.0, 1.0)
                self.combo = max(0, self.combo - 1 if self.combo_timer <= 0 else self.combo)
        else:
            self.precision_meter = clamp(self.precision_meter - 0.4 * dt, 0.0, 1.0)
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = max(0, self.combo - 1)

        # Update particles
        for p in self.sparks:
            p.update(dt)
        self.sparks = [p for p in self.sparks if p.life > 0]
        self.perfect_alpha = max(0.0, self.perfect_alpha - dt * 1.2)

    def finish_game(self):
        score = int(self.precision_score * 10 + self.precision_meter * 100)
        self.app.push(HighScoreGate(self.app, mode="precision", score=score, on_continue=lambda: self.app.replace(HighScoreBoard(self.app, mode="precision"))))

    def draw_head_view(self, dst: Surface):
        # First-person: linkerkant hoofd met fade-zone aanduiding
        mx, my = self.mouse_pos
        head_rect = Rect(WIDTH // 2 - 220, HEIGHT // 2 - 140, 220, 280)
        # Haar vlak
        pygame.draw.rect(dst, (30, 30, 30), head_rect, border_radius=18)
        pygame.draw.rect(dst, COLORS["BLACK"], head_rect, width=6, border_radius=18)
        # Fade target: gradient overlay (blauw)
        grad = pygame.Surface((head_rect.w, head_rect.h), pygame.SRCALPHA)
        for i in range(head_rect.h):
            t = i / head_rect.h
            intensity = int(80 * (1.0 - abs(0.6 - t)))
            col = (COLORS["ELECTRIC_BLUE"][0], COLORS["ELECTRIC_BLUE"][1], COLORS["ELECTRIC_BLUE"][2], clamp(intensity, 0, 120))
            pygame.draw.line(grad, col, (0, i), (head_rect.w, i))
        dst.blit(grad, head_rect)
        # Sweet zone band
        band = Rect(head_rect.x - 20, self.sweet_y0, head_rect.w + 40, self.sweet_y1 - self.sweet_y0)
        band_surf = pygame.Surface(band.size, pygame.SRCALPHA)
        band_surf.fill((COLORS["ELECTRIC_BLUE"][0], COLORS["ELECTRIC_BLUE"][1], COLORS["ELECTRIC_BLUE"][2], 30))
        dst.blit(band_surf, band)
        pygame.draw.rect(dst, COLORS["ELECTRIC_BLUE"], band, width=4)

        # Tondeuse (cursor)
        draw_clippers(dst, (mx, my), scale=1.0)

    def draw_ui(self, dst: Surface):
        # Time Limit bar (boven, rood knipperend bij weinig tijd)
        tl = self.time_left
        ratio = clamp(tl / self.time_limit, 0.0, 1.0)
        bar_w = 460
        bar_h = 18
        x = WIDTH // 2 - bar_w // 2
        y = 18
        pygame.draw.rect(dst, COLORS["WHITE"], Rect(x - 4, y - 4, bar_w + 8, bar_h + 8), border_radius=10)
        bg_col = COLORS["GREY"]
        pygame.draw.rect(dst, bg_col, Rect(x, y, bar_w, bar_h), border_radius=8)
        fill_col = COLORS["RED"] if tl < 8.0 and int(pygame.time.get_ticks() / 250) % 2 == 0 else COLORS["NEON_RED"]
        pygame.draw.rect(dst, fill_col, Rect(x, y, int(bar_w * ratio), bar_h), border_radius=8)
        # Label
        label, _ = self.app.font_small.render("TIME LIMIT", COLORS["WHITE"])
        dst.blit(label, (x, y - 22))

        # Verticale precisiemeter (rechts)
        meter_h = 220
        mx = WIDTH - 60
        my = HEIGHT // 2 - meter_h // 2
        pygame.draw.rect(dst, COLORS["WHITE"], Rect(mx - 12, my - 12, 40, meter_h + 24), border_radius=10)
        pygame.draw.rect(dst, COLORS["GREY"], Rect(mx, my, 16, meter_h), border_radius=8)
        filled = int(meter_h * self.precision_meter)
        pygame.draw.rect(dst, COLORS["ELECTRIC_BLUE"], Rect(mx, my + meter_h - filled, 16, filled), border_radius=8)
        txt, rect = self.app.font_small.render("PRECISION", COLORS["WHITE"]) 
        dst.blit(txt, (mx - rect.width // 2 - 2, my + meter_h + 12))

        # Float: PERFECT FADE!
        if self.perfect_alpha > 0.0:
            alpha = int(255 * self.perfect_alpha)
            text, rect = self.app.font_big.render("PERFECT FADE!", fgcolor=COLORS["ELECTRIC_BLUE"])
            text_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
            text_surf.blit(text, (0, 0))
            text_surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
            dst.blit(text_surf, (WIDTH // 2 - rect.width // 2, HEIGHT // 2 - 200))

        # Score en combo
        s = f"Score: {int(self.precision_score * 10)}  Combo: {self.combo}"
        surf, r = self.app.font_small.render(s, COLORS["WHITE"])
        dst.blit(surf, (18, 18))

    def draw(self, dst: Surface):
        draw_barbershop_bg(dst)
        self.draw_head_view(dst)
        # De- focus DOF effect (wazige achtergrond al gesuggereerd in bg)
        # Vonken tekenen
        for p in self.sparks:
            p.draw(dst)
        self.draw_ui(dst)

# ------------------------------------------------------------
# Game 2: Street Brawl (mini)
# ------------------------------------------------------------
@dataclass
class Fighter:
    name: str
    x: float
    y: float
    facing: int  # 1 of -1
    hp: int = 100
    super_meter: float = 0.0  # 0..100
    on_ground: bool = True
    vy: float = 0.0
    state: str = "idle"  # idle, walk, attack, super, dodge, hit
    state_timer: float = 0.0

    def rect(self) -> Rect:
        return Rect(int(self.x) - 40, int(self.y) - 110, 80, 110)


class StreetBrawlGame(Scene):
    def __init__(self, app: GameApp):
        super().__init__(app)
        # Arena
        self.floor_y = HEIGHT - 180
        self.timer = 99.0
        # Fighters: Tank (P1) vs Technicus (AI)
        self.p1 = Fighter("Tank", x=WIDTH * 0.35, y=self.floor_y, facing=1)
        self.p2 = Fighter("Technicus", x=WIDTH * 0.65, y=self.floor_y, facing=-1)
        self.particles: List[Particle] = []
        self.shockwaves: List[Tuple[float, float, float, float]] = []  # (x,y,radius,life)
        self.keys = set()

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.app.pop()
                return
            self.keys.add(e.key)
        elif e.type == pygame.KEYUP:
            if e.key in self.keys:
                self.keys.remove(e.key)

    def update(self, dt: float):
        self.timer -= dt
        if self.timer <= 0 or self.p1.hp <= 0 or self.p2.hp <= 0:
            self.finish_game()
            return
        # Input P1
        move = 0
        if pygame.K_a in self.keys:
            move -= 1
        if pygame.K_d in self.keys:
            move += 1
        if move != 0:
            self.p1.x += move * 160 * dt
            self.p1.facing = 1 if move > 0 else -1
            self.p1.state = "walk"
        else:
            if self.p1.state not in ("attack", "super", "hit"):
                self.p1.state = "idle"
        if pygame.K_w in self.keys and self.p1.on_ground:
            self.p1.on_ground = False
            self.p1.vy = -320
        if pygame.K_j in self.keys and self.p1.state not in ("attack", "super"):
            self.p1.state = "attack"
            self.p1.state_timer = 0.25
            self.try_hit(self.p1, self.p2, dmg=6, impulse=140)
            self.p1.super_meter = clamp(self.p1.super_meter + 8, 0, 100)
        if pygame.K_k in self.keys and self.p1.super_meter >= 100 and self.p1.state != "super":
            self.p1.state = "super"
            self.p1.state_timer = 0.8
            self.p1.super_meter = 0
            # Super: gloeiende vuist + scheerschuim schokgolf
            sx = self.p1.x + self.p1.facing * 40
            sy = self.p1.y - 60
            self.shockwaves.append([sx, sy, 10.0, 0.5])
            for _ in range(24):
                ang = random.random() * 2 * math.pi
                spd = 200 + random.random() * 260
                col = COLORS["WHITE"] if random.random() < 0.5 else COLORS["ELECTRIC_BLUE"]
                self.particles.append(Particle(sx, sy, math.cos(ang) * spd, math.sin(ang) * spd, 0.6 + random.random() * 0.6, col, size=3, gravity=30))
            self.try_hit(self.p1, self.p2, dmg=18, impulse=240, wide=True)

        # Gravity
        for f in (self.p1, self.p2):
            if not f.on_ground:
                f.vy += 800 * dt
                f.y += f.vy * dt
                if f.y >= self.floor_y:
                    f.y = self.floor_y
                    f.vy = 0
                    f.on_ground = True

        # AI P2
        self.ai_update(self.p2, self.p1, dt)

        # State timers
        for f in (self.p1, self.p2):
            if f.state_timer > 0:
                f.state_timer -= dt
                if f.state_timer <= 0 and f.state in ("attack", "super", "hit", "dodge"):
                    f.state = "idle"

        # Shockwaves expand
        for sw in self.shockwaves:
            sw[2] += 600 * dt
            sw[3] -= dt
        self.shockwaves = [sw for sw in self.shockwaves if sw[3] > 0]

        # Particles
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]

        # Clamp in arena
        self.p1.x = clamp(self.p1.x, 100, WIDTH - 100)
        self.p2.x = clamp(self.p2.x, 100, WIDTH - 100)

    def try_hit(self, a: Fighter, b: Fighter, dmg: int, impulse: float, wide: bool = False):
        ar = a.rect()
        if wide:
            hitbox = Rect(ar.centerx + a.facing * 0, ar.y + 10, 220, 90) if a.facing > 0 else Rect(ar.centerx - 220, ar.y + 10, 220, 90)
        else:
            hitbox = Rect(ar.centerx + a.facing * 20, ar.y + 10, 60, 60) if a.facing > 0 else Rect(ar.centerx - 80, ar.y + 10, 60, 60)
        if hitbox.colliderect(b.rect()):
            b.hp = max(0, b.hp - dmg)
            b.state = "hit"
            b.state_timer = 0.3
            b.vy = -120
            b.on_ground = False
            b.x += a.facing * impulse * 0.05
            # Foam burst
            for _ in range(8):
                self.particles.append(Particle(hitbox.centerx, hitbox.centery, random.uniform(-80, 80), random.uniform(-20, -180), 0.4, COLORS["WHITE"], size=3, gravity=200))

    def ai_update(self, me: Fighter, target: Fighter, dt: float):
        # Simple AI: hou afstand, dodge bij shockwave
        dist = target.x - me.x
        me.facing = 1 if dist > 0 else -1
        if abs(dist) < 180:
            me.x -= me.facing * 120 * dt
            me.state = "walk"
            if random.random() < 0.02:
                me.state = "dodge"
                me.state_timer = 0.2
                me.x -= me.facing * 120 * dt * 6
        else:
            me.state = "idle"
        # Sporadisch jump back
        if random.random() < 0.01 and me.on_ground:
            me.on_ground = False
            me.vy = -260
            me.x -= me.facing * 80

    def finish_game(self):
        # Score op basis van tegenstander HP en resterende tijd
        base = 100 if self.p2.hp <= 0 else 60 if self.p1.hp > self.p2.hp else 30
        score = base + int(self.p2.hp * -0.5 + self.p1.hp * 0.8 + self.timer)
        score = max(0, score)
        self.app.push(HighScoreGate(self.app, mode="brawl", score=score, on_continue=lambda: self.app.replace(HighScoreBoard(self.app, mode="brawl"))))

    def draw_bg(self, dst: Surface):
        draw_barbershop_bg(dst)
        # Stoelen aan de kant
        for i in range(3):
            draw_vintage_chair(dst, (220 + i * 320, self.floor_y + 10), scale=0.8)
        # Ring/floor line
        pygame.draw.line(dst, COLORS["BLACK"], (60, self.floor_y + 2), (WIDTH - 60, self.floor_y + 2), 6)

    def draw_fighter(self, dst: Surface, f: Fighter, palette: Tuple[int, int, int]):
        pos = (int(f.x), int(f.y) - 10)
        scale = 1.2 if f.name == "Tank" else 1.1
        # Ready or action poses
        arche = "tank" if f.name == "Tank" else "technicus"
        draw_character(dst, pos, scale, palette, arche)
        # Effects
        if f.state == "super" and f.name == "Tank":
            # Glowing fist
            fx = f.x + f.facing * 46
            fy = f.y - 60
            draw_flaming_fist(dst, (int(fx), int(fy)), scale=1.0)

    def draw_ui(self, dst: Surface):
        # Health bars boven
        def draw_bar(x, y, w, h, value, color):
            pygame.draw.rect(dst, COLORS["WHITE"], Rect(x - 4, y - 4, w + 8, h + 8), border_radius=8)
            pygame.draw.rect(dst, COLORS["GREY"], Rect(x, y, w, h), border_radius=6)
            pygame.draw.rect(dst, color, Rect(x, y, int(w * clamp(value, 0.0, 1.0)), h), border_radius=6)

        w = 420
        h = 18
        draw_bar(60, 20, w, h, self.p1.hp / 100.0, COLORS["YELLOW"])
        draw_bar(WIDTH - 60 - w, 20, w, h, self.p2.hp / 100.0, COLORS["GREEN"])
        # Portretten (mini icons)
        pygame.draw.circle(dst, COLORS["YELLOW"], (40, 30), 16)
        pygame.draw.circle(dst, COLORS["GREEN"], (WIDTH - 40, 30), 16)
        # Timer midden
        t = int(self.timer)
        surf, r = self.app.font.render(f"{t:02d}", COLORS["WHITE"]) 
        dst.blit(surf, (WIDTH // 2 - r.width // 2, 12))

        # Super meters onderin
        def draw_super(x, y, value):
            W = 260
            H = 10
            pygame.draw.rect(dst, COLORS["WHITE"], Rect(x - 3, y - 3, W + 6, H + 6), border_radius=6)
            pygame.draw.rect(dst, (40, 40, 40), Rect(x, y, W, H), border_radius=6)
            glow = int(W * clamp(value / 100.0, 0.0, 1.0))
            col = COLORS["ELECTRIC_BLUE"]
            pygame.draw.rect(dst, col, Rect(x, y, glow, H), border_radius=6)
            if value >= 100 and int(pygame.time.get_ticks() / 150) % 2 == 0:
                pygame.draw.rect(dst, COLORS["WHITE"], Rect(x, y, W, H), width=2, border_radius=6)

        draw_super(80, HEIGHT - 50, self.p1.super_meter)
        draw_super(WIDTH - 80 - 260, HEIGHT - 50, self.p2.super_meter)

    def draw(self, dst: Surface):
        self.draw_bg(dst)
        # Shockwaves behind/on top ordering
        for sw in self.shockwaves:
            x, y, r, life = sw
            alpha = int(180 * life)
            pygame.draw.circle(dst, (255, 255, 255, alpha), (int(x), int(y)), int(r), width=6)
        self.draw_fighter(dst, self.p1, (150, 70, 50))
        self.draw_fighter(dst, self.p2, (60, 60, 140))
        # Foam particles
        for p in self.particles:
            p.draw(dst)
        self.draw_ui(dst)

# ------------------------------------------------------------
# High Score Scenes
# ------------------------------------------------------------
class HighScoreGate(Scene):
    def __init__(self, app: GameApp, mode: str, score: int, on_continue: Callable[[], None]):
        super().__init__(app)
        self.mode = mode
        self.score = score
        self.on_continue = on_continue
        # Check of score in top 10 komt
        scores = sorted(self.app.highscores.get(mode, []), key=lambda s: s.get("score", 0), reverse=True)
        if len(scores) < 10 or (scores and score > scores[-1].get("score", -1)) or not scores:
            self.qualify = True
        else:
            self.qualify = False
        self.name = ""

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if self.qualify:
                if e.key == pygame.K_RETURN:
                    self.submit_and_continue()
                elif e.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                else:
                    ch = e.unicode
                    if ch and (ch.isalnum() or ch in (" ", "_", "-")) and len(self.name) < 12:
                        self.name += ch
            else:
                if e.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    self.on_continue()

    def submit_and_continue(self):
        entry = {"name": self.name or "ANON", "score": int(self.score)}
        arr = self.app.highscores.setdefault(self.mode, [])
        arr.append(entry)
        arr.sort(key=lambda s: s.get("score", 0), reverse=True)
        del arr[10:]
        save_highscores(self.app.highscores)
        self.on_continue()

    def update(self, dt: float):
        pass

    def draw(self, dst: Surface):
        draw_barbershop_bg(dst)
        # Title
        title = "NEW HIGH SCORE!" if self.qualify else "GAME OVER"
        col = COLORS["ELECTRIC_BLUE"] if self.mode == "precision" else COLORS["NEON_RED"]
        draw_neon_text(dst, title, self.app.font_big, (WIDTH // 2, 120), col, col, center=True)
        # Score
        s = f"Score: {self.score}"
        surf, r = self.app.font.render(s, COLORS["WHITE"])
        dst.blit(surf, (WIDTH // 2 - r.width // 2, 220))
        if self.qualify:
            s2 = "Voer je naam in (Enter om te bevestigen):"
            surf2, r2 = self.app.font_small.render(s2, COLORS["WHITE"])
            dst.blit(surf2, (WIDTH // 2 - r2.width // 2, 280))
            box = Rect(WIDTH // 2 - 240, 320, 480, 50)
            pygame.draw.rect(dst, COLORS["WHITE"], box, width=3, border_radius=8)
            name_surf, name_r = self.app.font.render(self.name or "_", COLORS["WHITE"])
            dst.blit(name_surf, (box.centerx - name_r.width // 2, box.centery - name_r.height // 2))
        else:
            s3 = "Druk op Enter om verder te gaan"
            surf3, r3 = self.app.font_small.render(s3, COLORS["WHITE"])
            dst.blit(surf3, (WIDTH // 2 - r3.width // 2, 300))


class HighScoreBoard(Scene):
    def __init__(self, app: GameApp, mode: str):
        super().__init__(app)
        self.mode = mode

    def handle_event(self, e: pygame.event.Event):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                # terug naar menu
                # pop tot menu overblijft
                while len(self.app.scenes) > 1:
                    self.app.pop()

    def update(self, dt: float):
        pass

    def draw(self, dst: Surface):
        draw_barbershop_bg(dst)
        title = f"HIGH SCORES - {'PRECISION CUT' if self.mode == 'precision' else 'STREET BRAWL'}"
        col = COLORS["ELECTRIC_BLUE"] if self.mode == "precision" else COLORS["NEON_RED"]
        draw_neon_text(dst, title, self.app.font, (WIDTH // 2, 100), col, col, center=True)
        scores = sorted(self.app.highscores.get(self.mode, []), key=lambda s: s.get("score", 0), reverse=True)
        if not scores:
            scores = [{"name": "---", "score": 0}]
        y = 180
        for i, item in enumerate(scores[:10], start=1):
            row = f"{i:2d}. {item.get('name','---'):<12}   {item.get('score',0):>6}"
            surf, r = self.app.font_small.render(row, COLORS["WHITE"])
            dst.blit(surf, (WIDTH // 2 - r.width // 2, y))
            y += 40
        hint = "Enter/Esc: terug naar menu"
        surf, r = self.app.font_small.render(hint, COLORS["WHITE"])
        dst.blit(surf, (WIDTH // 2 - r.width // 2, HEIGHT - 60))

# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    app = GameApp()
    app.run()
