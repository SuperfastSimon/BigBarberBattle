#!/usr/bin/env python3
# Voorbeeld game prototype in Python (pygame-ce)
# Installatie: pip install -r requirements.txt
# Start: python main.py
from __future__ import annotations
import os
import sys
import json
import time
from dataclasses import dataclass
from typing import Optional, Callable
import pygame as pg

# Globals
WIDTH, HEIGHT = 1280, 720
FPS = 60
TITLE = "Barber Brawl & Precision Cut"
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(DATA_DIR, "highscores.json")

# Kleuren (palette)
BLACK = pg.Color(10, 10, 12)
NEON_RED = pg.Color(255, 43, 43)
ELECTRIC_BLUE = pg.Color(43, 217, 255)
WOOD_DARK = pg.Color(90, 62, 43)
WOOD_LIGHT = pg.Color(130, 94, 64)
GOLD = pg.Color(255, 197, 66)
WHITE = pg.Color(240, 240, 240)
GREY = pg.Color(160, 160, 160)
GREEN = pg.Color(60, 220, 120)
YELLOW = pg.Color(255, 228, 86)
RED = pg.Color(240, 60, 60)

# Font helpers
_fonts: dict[tuple[int, bool], pg.font.Font] = {}

def get_font(size: int, bold: bool = False) -> pg.font.Font:
    key = (size, bold)
    if key not in _fonts:
        f = pg.font.SysFont("arial", size, bold=bold)
        _fonts[key] = f
    return _fonts[key]

# Util: outlined text (thick)

def draw_outlined_text(surf: pg.Surface, text: str, pos: tuple[int, int], color: pg.Color, outline: pg.Color = pg.Color(0,0,0), size: int = 36, bold: bool = True, center: bool = False):
    font = get_font(size, bold)
    base = font.render(text, True, color)
    ox, oy = pos
    if center:
        rect = base.get_rect(center=(ox, oy))
    else:
        rect = base.get_rect(topleft=(ox, oy))
    # outline
    for dx, dy in ((-2,0),(2,0),(0,-2),(0,2),(-2,-2),(2,-2),(-2,2),(2,2)):
        outline_img = font.render(text, True, outline)
        orect = outline_img.get_rect(center=rect.center)
        orect.move_ip(dx, dy)
        surf.blit(outline_img, orect)
    surf.blit(base, rect)

# Glow text (neon)

def draw_neon_text(surf: pg.Surface, text: str, center: tuple[int, int], color: pg.Color = NEON_RED, size: int = 48):
    font = get_font(size, True)
    text_surf = font.render(text, True, color)
    rect = text_surf.get_rect(center=center)
    # Glow layers
    glow = pg.Surface((rect.w+60, rect.h+60), pg.SRCALPHA)
    grect = glow.get_rect(center=center)
    for r, alpha in ((8, 40), (16, 26), (28, 14)):
        glow_layer = font.render(text, True, color)
        layer = pg.Surface(glow_layer.get_size(), pg.SRCALPHA)
        layer.blit(glow_layer, (0,0))
        layer = pg.transform.smoothscale(layer, (int(layer.get_width()*1.08), int(layer.get_height()*1.08)))
        layer2 = pg.Surface(glow.get_size(), pg.SRCALPHA)
        layer2.blit(layer, ((glow.get_width()-layer.get_width())//2, (glow.get_height()-layer.get_height())//2))
        # fill and blur-ish by multiple blits
        blurred = pg.Surface(glow.get_size(), pg.SRCALPHA)
        for dx in range(-r, r+1, r//4 if r//4 else 1):
            for dy in range(-r, r+1, r//4 if r//4 else 1):
                blurred.blit(layer2, (dx, dy))
        tinted = pg.Surface(blurred.get_size(), pg.SRCALPHA)
        tinted.fill((*color, alpha))
        blurred.blit(tinted, (0,0), special_flags=pg.BLEND_RGBA_MULT)
        glow.blit(blurred, (0,0))
    surf.blit(glow, grect)
    # core text
    surf.blit(text_surf, rect)

# Particle system (sparks / foam)
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    color: pg.Color
    life: float
    t: float = 0.0
    def update(self, dt: float):
        self.t += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        # gravity-ish for foam less; for sparks more
        self.vy += 300 * dt
        self.r = max(0.5, self.r * (1 - 0.9*dt))
    def draw(self, surf: pg.Surface):
        if self.t < self.life:
            alpha = max(0, int(255 * (1 - self.t / self.life)))
            pg.draw.circle(surf, (*self.color[:3], alpha), (int(self.x), int(self.y)), int(self.r))

# Scene base
class Scene:
    def __init__(self, game: 'Game'): self.game = game
    def start(self): pass
    def handle_event(self, e: pg.event.Event): pass
    def update(self, dt: float): pass
    def draw(self, surf: pg.Surface): pass

# Highscore manager
class HighScores:
    def __init__(self, path: str):
        self.path = path
        self.data: dict[str, list[dict]] = {"precision_cut": [], "street_brawl": []}
        self.load()
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {"precision_cut": [], "street_brawl": []}
    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    def add_score(self, board: str, name: str, score: int):
        self.data.setdefault(board, [])
        self.data[board].append({"name": name[:16], "score": int(score)})
        self.data[board] = sorted(self.data[board], key=lambda x: x["score"], reverse=True)[:10]
        self.save()
    def qualifies(self, board: str, score: int) -> bool:
        scores = self.data.get(board, [])
        if len(scores) < 10: return True
        return score > scores[-1]["score"]

# Simple shapes for icons/characters
class Shapes:
    @staticmethod
    def thick_rect(surf, color, rect, border=6):
        pg.draw.rect(surf, pg.Color(0,0,0), rect.inflate(border*2, border*2), border_radius=8)
        pg.draw.rect(surf, color, rect, border_radius=8)
    @staticmethod
    def barber_chair(surf, center, scale=1.0, color=WOOD_LIGHT):
        x,y = center
        w,h = int(160*scale), int(160*scale)
        # seat
        seat = pg.Rect(x-w//3, y-h//6, w//1.5, h//4)
        pg.draw.rect(surf, pg.Color(0,0,0), seat.inflate(10,10), border_radius=8)
        pg.draw.rect(surf, color, seat, border_radius=8)
        # backrest
        back = pg.Rect(seat.x, seat.y-h//3, seat.w, h//3)
        pg.draw.rect(surf, pg.Color(0,0,0), back.inflate(10,10), border_radius=8)
        pg.draw.rect(surf, color, back, border_radius=8)
        # base and footrest
        base = pg.Rect(x-12, seat.bottom, 24, 60)
        pg.draw.rect(surf, pg.Color(0,0,0), base.inflate(8,8))
        pg.draw.rect(surf, GREY, base)
        foot = pg.Rect(x-w//5, base.bottom-8, w//2.5, 12)
        pg.draw.rect(surf, pg.Color(0,0,0), foot.inflate(8,8))
        pg.draw.rect(surf, GREY, foot)
    @staticmethod
    def scissors(surf, center, scale=1.0, color=GOLD):
        x,y = center
        # blades
        for angle in (-25, 25):
            end = (int(x + 120*scale*pg.math.Vector2(1,0).rotate(angle).x), int(y + 120*scale*pg.math.Vector2(1,0).rotate(angle).y))
            pg.draw.line(surf, pg.Color(0,0,0), (x,y), end, 10)
            pg.draw.line(surf, color, (x,y), end, 6)
        # handles
        for dx,dy in ((-30,-20),(-30,20)):
            pg.draw.circle(surf, pg.Color(0,0,0), (x+int(dx*scale), y+int(dy*scale)), int(24*scale)+4, 8)
            pg.draw.circle(surf, color, (x+int(dx*scale), y+int(dy*scale)), int(24*scale), 6)
    @staticmethod
    def clippers(surf, center, scale=1.0, color=GOLD):
        x,y = center
        body = pg.Rect(0,0,int(60*scale),int(140*scale)); body.center=(x,y)
        pg.draw.rect(surf, pg.Color(0,0,0), body.inflate(10,10), border_radius=16)
        pg.draw.rect(surf, color, body, border_radius=16)
        teeth = pg.Rect(body.x, body.top-16, body.w, 16)
        pg.draw.rect(surf, pg.Color(0,0,0), teeth)
        for i in range(0, body.w, 8):
            pg.draw.rect(surf, WHITE, (teeth.x+i+2, teeth.y+2, 4, 12))
    @staticmethod
    def flaming_fist(surf, center, scale=1.0):
        x,y = center
        # fist
        fist = pg.Rect(0,0,int(120*scale), int(80*scale)); fist.center=(x,y)
        pg.draw.rect(surf, pg.Color(0,0,0), fist.inflate(10,10), border_radius=12)
        pg.draw.rect(surf, YELLOW, fist, border_radius=12)
        # flames
        for i, c in enumerate([(255,120,0), (255,60,0), (255,200,0)]):
            flame = pg.Surface((int(200*scale), int(140*scale)), pg.SRCALPHA)
            for a in range(0, 360, 30):
                v = pg.math.Vector2(1,0).rotate(a)
                end = (flame.get_width()//2 + int(v.x*80*scale), flame.get_height()//2 - int(abs(v.y)*60*scale))
                pg.draw.polygon(flame, (*c, 80-i*20), [(flame.get_width()//2, flame.get_height()//2), end, (end[0], end[1]-10)])
            surf.blit(flame, (x-flame.get_width()//2, y-flame.get_height()//2), special_flags=pg.BLEND_ADD)

# Background: industrial barbershop with neon sign

def draw_barbershop_bg(surf: pg.Surface):
    surf.fill(BLACK)
    # floor and walls
    wall = pg.Rect(0,0,WIDTH, HEIGHT*0.65)
    floor = pg.Rect(0, wall.bottom, WIDTH, HEIGHT - wall.bottom)
    pg.draw.rect(surf, pg.Color(20,20,26), wall)
    # wood panels
    for i in range(0, WIDTH, 80):
        r = pg.Rect(i, wall.bottom-60, 70, 60)
        pg.draw.rect(surf, WOOD_DARK, r)
        pg.draw.rect(surf, WOOD_LIGHT, r.inflate(-10,-10))
    pg.draw.rect(surf, pg.Color(30,20,16), floor)
    # mirrors blurred
    for i in range(3):
        mirror = pg.Rect(120 + i*360, 90, 260, 200)
        pg.draw.rect(surf, pg.Color(0,0,0), mirror.inflate(8,8), border_radius=6)
        pg.draw.rect(surf, pg.Color(60,70,80), mirror, border_radius=6)
        glare = pg.Surface((mirror.w, mirror.h), pg.SRCALPHA)
        for a in range(0, 60, 6):
            pg.draw.line(glare, (200,220,255, 12), (0, a), (mirror.w, a//2))
        surf.blit(glare, mirror)
    # chairs pushed aside
    Shapes.barber_chair(surf, (200, 430), 0.9)
    Shapes.barber_chair(surf, (1060, 430), 0.9)
    # neon sign
    draw_neon_text(surf, "IT'S A CUT-THROAT BUSINESS", (WIDTH//2, 60), NEON_RED, size=44)

# UI elements

def draw_health_bar(surf, x, y, w, h, value, max_value, name, face_color):
    pg.draw.rect(surf, pg.Color(0,0,0), (x-4,y-4,w+8,h+8), border_radius=6)
    # gradient-ish
    ratio = max(0, min(1, value / max_value))
    fill_w = int(w * ratio)
    color = GREEN if ratio > 0.5 else (YELLOW if ratio > 0.25 else RED)
    pg.draw.rect(surf, pg.Color(50,50,50), (x,y,w,h), border_radius=4)
    pg.draw.rect(surf, color, (x,y,fill_w,h), border_radius=4)
    # portrait
    face = pg.Rect(x - h - 16, y, h, h)
    pg.draw.rect(surf, pg.Color(0,0,0), face.inflate(8,8), border_radius=6)
    pg.draw.rect(surf, face_color, face, border_radius=6)
    draw_outlined_text(surf, name, (x + w//2, y + h//2), WHITE, size=18, bold=True, center=True)


def draw_timer(surf, t):
    draw_outlined_text(surf, f"{int(t):02d}", (WIDTH//2, 30), WHITE, size=36, bold=True, center=True)


def draw_super_meter(surf, x, y, w, h, value, max_value):
    pg.draw.rect(surf, pg.Color(0,0,0), (x-4,y-4,w+8,h+8), border_radius=6)
    ratio = max(0, min(1, value / max_value))
    glow = pg.Surface((w, h), pg.SRCALPHA)
    col = ELECTRIC_BLUE
    pg.draw.rect(glow, (*col, 220), (0,0,int(w*ratio),h), border_radius=4)
    for i in range(3):
        surf.blit(glow, (x, y), special_flags=pg.BLEND_ADD)
    pg.draw.rect(surf, WHITE, (x,y,w,h), 2, border_radius=4)


def draw_time_limit_bar(surf, remaining_ratio: float):
    w, h = 420, 18
    x, y = (WIDTH - w)//2, 8
    pg.draw.rect(surf, pg.Color(0,0,0), (x-3,y-3,w+6,h+6), border_radius=6)
    fill_w = int(w * remaining_ratio)
    col = NEON_RED if remaining_ratio < 0.25 and int(pg.time.get_ticks()/200)%2==0 else YELLOW
    pg.draw.rect(surf, pg.Color(40,40,40), (x,y,w,h), border_radius=4)
    pg.draw.rect(surf, col, (x,y,fill_w,h), border_radius=4)
    draw_outlined_text(surf, "TIME LIMIT", (x-80, y+h//2), WHITE, size=18, bold=True)


def draw_precision_meter(surf, x, y, h, value_ratio: float):
    w = 14
    pg.draw.rect(surf, pg.Color(0,0,0), (x-3,y-3,w+6,h+6), border_radius=6)
    pg.draw.rect(surf, pg.Color(45,45,55), (x,y,w,h), border_radius=4)
    # target center
    center_y = y + h//2
    pg.draw.line(surf, ELECTRIC_BLUE, (x, center_y), (x+w, center_y), 2)
    marker_y = y + int(h * (1 - value_ratio))
    pg.draw.rect(surf, ELECTRIC_BLUE, (x+2, marker_y-6, w-4, 12), border_radius=4)

# Menu scene
class Menu(Scene):
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.hover_left = False
        self.hover_right = False
    def handle_event(self, e: pg.event.Event):
        if e.type == pg.MOUSEMOTION:
            mx,my = e.pos
            self.hover_left = mx < WIDTH//2
            self.hover_right = mx >= WIDTH//2
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            mx,my = e.pos
            if mx < WIDTH//2:
                self.game.change_scene(PrecisionCut(self.game))
            else:
                self.game.change_scene(StreetBrawl(self.game))
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_1, pg.K_a, pg.K_LEFT):
                self.game.change_scene(PrecisionCut(self.game))
            elif e.key in (pg.K_2, pg.K_d, pg.K_RIGHT):
                self.game.change_scene(StreetBrawl(self.game))
    def draw(self, surf: pg.Surface):
        draw_barbershop_bg(surf)
        # split overlay
        left_rect = pg.Rect(0, 120, WIDTH//2, HEIGHT-160)
        right_rect = pg.Rect(WIDTH//2, 120, WIDTH//2, HEIGHT-160)
        lcol = pg.Color(30, 30, 40, 180)
        rcol = pg.Color(20, 20, 30, 180)
        lsurf = pg.Surface((left_rect.w, left_rect.h), pg.SRCALPHA)
        rsurf = pg.Surface((right_rect.w, right_rect.h), pg.SRCALPHA)
        lsurf.fill(lcol)
        rsurf.fill(rcol)
        surf.blit(lsurf, left_rect)
        surf.blit(rsurf, right_rect)
        # Left option: Precision Cut
        draw_outlined_text(surf, "PRECISION CUT", (left_rect.centerx, left_rect.top+30), ELECTRIC_BLUE, size=38, bold=True, center=True)
        # Icons: crossed scissors & clippers above chair
        Shapes.barber_chair(surf, (left_rect.centerx, left_rect.centery+60), 0.9)
        Shapes.scissors(surf, (left_rect.centerx-50, left_rect.centery-30), 0.8)
        Shapes.clippers(surf, (left_rect.centerx+50, left_rect.centery-30), 0.8)
        draw_outlined_text(surf, "Focus. Kalmte. Ambacht.", (left_rect.centerx, left_rect.bottom-40), WHITE, size=22, center=True)
        if self.hover_left:
            pg.draw.rect(surf, ELECTRIC_BLUE, left_rect, 4)
        # Right option: Street Brawl
        draw_outlined_text(surf, "STREET BRAWL", (right_rect.centerx, right_rect.top+30), NEON_RED, size=38, bold=True, center=True)
        # Flaming fist icon
        Shapes.flaming_fist(surf, (right_rect.centerx, right_rect.top+110), 1.0)
        # Characters lineup silhouettes (A,B,C,D)
        self.draw_character_lineup(surf, right_rect)
        if self.hover_right:
            pg.draw.rect(surf, NEON_RED, right_rect, 4)
        # Hint
        draw_outlined_text(surf, "Klik links of rechts • 1/2", (WIDTH//2, HEIGHT-24), WHITE, size=20, center=True)
    def draw_character_lineup(self, surf: pg.Surface, rect: pg.Rect):
        base_y = rect.bottom - 120
        spacing = rect.w // 5
        x0 = rect.left + spacing
        # Character A: Tank (beard, tattoos, arms crossed)
        self.draw_character(surf, (x0, base_y), body_col=pg.Color(180,80,60), outline=True, pose='tank')
        # B: All-rounder (Ryu archetype stance)
        self.draw_character(surf, (x0+spacing, base_y), body_col=pg.Color(200,180,160), outline=True, pose='ryu')
        # C: Brawler (E.Honda style)
        self.draw_character(surf, (x0+spacing*2, base_y), body_col=pg.Color(180,130,90), outline=True, pose='honda')
        # D: Technicus (glasses, scissors)
        self.draw_character(surf, (x0+spacing*3, base_y), body_col=pg.Color(160,140,120), outline=True, pose='vega')
    def draw_character(self, surf: pg.Surface, center: tuple[int,int], body_col: pg.Color, outline: bool, pose: str):
        x,y = center
        scale = 1.0
        # body
        torso = pg.Rect(0,0,70,110); torso.center=(x,y)
        if outline: pg.draw.rect(surf, pg.Color(0,0,0), torso.inflate(10,10), border_radius=12)
        pg.draw.rect(surf, body_col, torso, border_radius=12)
        # head
        head = pg.Rect(0,0,50,50); head.center=(x, y-80)
        if outline: pg.draw.ellipse(surf, pg.Color(0,0,0), head.inflate(8,8))
        pg.draw.ellipse(surf, body_col, head)
        # features per pose
        if pose == 'tank':
            # beard
            beard = pg.Rect(head.centerx-24, head.bottom-18, 48, 28)
            pg.draw.ellipse(surf, pg.Color(40,20,10), beard)
            # arms crossed
            pg.draw.line(surf, pg.Color(0,0,0), (x-40,y-10), (x+40,y+10), 12)
            pg.draw.line(surf, body_col, (x-40,y-10), (x+40,y+10), 8)
            pg.draw.line(surf, pg.Color(0,0,0), (x+40,y-10), (x-40,y+10), 12)
            pg.draw.line(surf, body_col, (x+40,y-10), (x-40,y+10), 8)
            # tattoos (dots)
            for i in range(-28,29,14):
                pg.draw.circle(surf, pg.Color(60,40,30), (x+i, y+30), 4)
        elif pose == 'ryu':
            # classic guard arms
            pg.draw.line(surf, pg.Color(0,0,0), (x-30,y), (x-10,y-20), 12)
            pg.draw.line(surf, body_col, (x-30,y), (x-10,y-20), 8)
            pg.draw.line(surf, pg.Color(0,0,0), (x+30,y-10), (x+8,y-20), 12)
            pg.draw.line(surf, body_col, (x+30,y-10), (x+8,y-20), 8)
            # headband
            pg.draw.line(surf, RED, (head.left, head.centery), (head.right, head.centery), 4)
        elif pose == 'honda':
            # big arms forward
            pg.draw.circle(surf, pg.Color(0,0,0), (x-40, y+5), 26)
            pg.draw.circle(surf, body_col, (x-40, y+5), 22)
            pg.draw.circle(surf, pg.Color(0,0,0), (x+40, y+5), 26)
            pg.draw.circle(surf, body_col, (x+40, y+5), 22)
        elif pose == 'vega':
            # glasses and mustache
            pg.draw.rect(surf, GREY, (head.centerx-18, head.centery-6, 36, 8))
            pg.draw.rect(surf, pg.Color(40,20,10), (head.centerx-14, head.bottom-16, 28, 6))
            # dynamic leg/arm
            pg.draw.line(surf, pg.Color(0,0,0), (x-30,y+10), (x+40,y-20), 12)
            pg.draw.line(surf, body_col, (x-30,y+10), (x+40,y-20), 8)
            # scissors in hand
            Shapes.scissors(surf, (x+48, y-24), 0.4)

# Precision Cut scene (first-person)
class PrecisionCut(Scene):
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.time_limit = 30.0
        self.time_left = self.time_limit
        self.sparks: list[Particle] = []
        self.clip_pos = [WIDTH*0.62, HEIGHT*0.52]
        self.target_curve: list[tuple[float,float]] = self.make_target_path()
        self.score = 0
        self.combo = 0
        self.show_perfect_t = 0.0
        self.done = False
        # vertical precision meter value 0..1 where 0.5 ideal
        self.precision_value = 0.5
    def make_target_path(self):
        # fade line along side of head: a curve
        pts = []
        base_x = WIDTH*0.62
        base_y = HEIGHT*0.35
        for i in range(40):
            t = i/39
            x = base_x + (pg.math.Vector2(0,-180).rotate(20*t*40).x)*0.2
            y = base_y + t*240 + (pg.math.Vector2(0,-180).rotate(90*t).y)*0.05
            pts.append((x,y))
        return pts
    def handle_event(self, e: pg.event.Event):
        if e.type == pg.KEYDOWN and self.done:
            if e.key == pg.K_RETURN:
                self.post_score_and_exit()
        if e.type == pg.MOUSEMOTION:
            self.clip_pos[0], self.clip_pos[1] = e.pos
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            self.emit_sparks(self.clip_pos[0], self.clip_pos[1])
    def emit_sparks(self, x, y):
        for i in range(24):
            ang = pg.math.Vector2(1,0).rotate(i*(360/24) + pg.rand.randint(-10,10))
            v = ang * pg.rand.uniform(120, 260)
            self.sparks.append(Particle(x, y, v.x, v.y-80, pg.rand.uniform(2,4), ELECTRIC_BLUE, pg.rand.uniform(0.3, 0.7)))
    def update(self, dt: float):
        if self.done:
            return
        keys = pg.key.get_pressed()
        speed = 420
        if keys[pg.K_a] or keys[pg.K_LEFT]: self.clip_pos[0]-=speed*dt
        if keys[pg.K_d] or keys[pg.K_RIGHT]: self.clip_pos[0]+=speed*dt
        if keys[pg.K_w] or keys[pg.K_UP]: self.clip_pos[1]-=speed*dt
        if keys[pg.K_s] or keys[pg.K_DOWN]: self.clip_pos[1]+=speed*dt
        # clamp
        self.clip_pos[0] = max(300, min(WIDTH-80, self.clip_pos[0]))
        self.clip_pos[1] = max(160, min(HEIGHT-80, self.clip_pos[1]))
        # precision check: distance to nearest target point
        cx, cy = self.clip_pos
        nearest = min(self.target_curve, key=lambda p: (p[0]-cx)**2+(p[1]-cy)**2)
        dist = pg.math.Vector2(cx-nearest[0], cy-nearest[1]).length()
        within = dist < 26
        self.precision_value = max(0.0, min(1.0, 0.5 + (nearest[1]-cy)/160))
        if within:
            self.combo += dt
            self.score += int(60*dt * (1 + min(5, self.combo)))
            # electric arcs periodically
            if int(pg.time.get_ticks()/100)%3==0:
                self.emit_sparks(cx, cy)
            if self.combo > 3 and self.show_perfect_t <= 0:
                self.show_perfect_t = 1.2
        else:
            self.combo = max(0.0, self.combo - 2*dt)
        self.time_left -= dt
        if self.time_left <= 0:
            self.done = True
        # update particles
        self.sparks = [p for p in self.sparks if p.t < p.life]
        for p in self.sparks: p.update(dt)
        self.show_perfect_t = max(0.0, self.show_perfect_t - dt)
    def draw(self, surf: pg.Surface):
        # Background with depth-of-field - blur fake via translucent overlays
        draw_barbershop_bg(surf)
        overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        overlay.fill((0,0,0, 80))
        surf.blit(overlay, (0,0))
        # head silhouette (left side of screen), cel-shaded
        head_center = (int(WIDTH*0.5), int(HEIGHT*0.52))
        head = pg.Rect(0,0,300,360); head.center = head_center
        pg.draw.ellipse(surf, pg.Color(0,0,0), head.inflate(16,16))
        pg.draw.ellipse(surf, pg.Color(50,50,58), head)
        # ear
        ear = pg.Rect(head.centerx+80, head.centery, 36, 46)
        pg.draw.ellipse(surf, pg.Color(0,0,0), ear.inflate(8,8))
        pg.draw.ellipse(surf, pg.Color(70,70,78), ear)
        # target fade path
        for (x1,y1), (x2,y2) in zip(self.target_curve, self.target_curve[1:]):
            pg.draw.line(surf, GREY, (x1,y1), (x2,y2), 3)
        # clippers (in hand)
        hand_x, hand_y = int(self.clip_pos[0]), int(self.clip_pos[1])
        # hand
        pg.draw.circle(surf, pg.Color(0,0,0), (hand_x-18, hand_y+18), 28)
        pg.draw.circle(surf, pg.Color(220,200,180), (hand_x-18, hand_y+18), 24)
        Shapes.clippers(surf, (hand_x, hand_y), 1.0)
        # sparks
        for p in self.sparks: p.draw(surf)
        # UI
        draw_time_limit_bar(surf, max(0.0, self.time_left / self.time_limit))
        draw_precision_meter(surf, WIDTH-40, 120, int(HEIGHT*0.6), self.precision_value)
        # Floating text
        if self.show_perfect_t > 0:
            alpha = int(255 * min(1, self.show_perfect_t))
            txtsurf = get_font(56, True).render("PERFECT FADE!", True, ELECTRIC_BLUE)
            txtsurf.set_alpha(alpha)
            rect = txtsurf.get_rect(center=(WIDTH//2, 120))
            surf.blit(txtsurf, rect)
        # Score
        draw_outlined_text(surf, f"SCORE: {self.score}", (16, 16), WHITE, size=24)
        if self.done:
            self.draw_end_overlay(surf)
    def draw_end_overlay(self, surf):
        dim = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA); dim.fill((0,0,0,180)); surf.blit(dim, (0,0))
        draw_outlined_text(surf, "TIME UP!", (WIDTH//2, HEIGHT//2-60), NEON_RED, size=56, center=True)
        draw_outlined_text(surf, f"SCORE: {self.score}", (WIDTH//2, HEIGHT//2), WHITE, size=36, center=True)
        if self.game.scores.qualifies("precision_cut", self.score):
            draw_outlined_text(surf, "Druk ENTER om je naam in te voeren", (WIDTH//2, HEIGHT//2+60), WHITE, size=24, center=True)
        else:
            draw_outlined_text(surf, "ENTER = Terug naar menu", (WIDTH//2, HEIGHT//2+60), WHITE, size=24, center=True)
    def post_score_and_exit(self):
        if self.game.scores.qualifies("precision_cut", self.score):
            self.game.change_scene(NameEntry(self.game, board="precision_cut", score=self.score, on_done=lambda: self.game.change_scene(HighScoreBoard(self.game, "precision_cut"))))
        else:
            self.game.change_scene(Menu(self.game))

# Street Brawl scene (2D fighting)
class Fighter:
    def __init__(self, name: str, color: pg.Color, facing: int):
        self.name = name
        self.color = color
        self.facing = facing  # 1 right, -1 left
        self.x = WIDTH*0.3 if facing==1 else WIDTH*0.7
        self.y = HEIGHT*0.7
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = True
        self.health = 1000
        self.super = 100
        self.state = 'idle'
        self.attack_cool = 0.0
        self.hurt_cool = 0.0
    @property
    def rect(self) -> pg.Rect:
        return pg.Rect(int(self.x-32), int(self.y-120), 64, 120)
    def update(self, dt: float):
        self.attack_cool = max(0.0, self.attack_cool - dt)
        self.hurt_cool = max(0.0, self.hurt_cool - dt)
        # gravity
        if not self.on_ground:
            self.vy += 1200*dt
            self.y += self.vy*dt
            if self.y >= HEIGHT*0.7:
                self.y = HEIGHT*0.7
                self.on_ground = True
                self.vy = 0
        # move
        self.x += self.vx*dt
        self.x = max(80, min(WIDTH-80, self.x))
    def draw(self, surf: pg.Surface):
        r = self.rect
        # outline torso
        pg.draw.rect(surf, pg.Color(0,0,0), r.inflate(12,12), border_radius=8)
        pg.draw.rect(surf, self.color, r, border_radius=8)
        # head
        head = pg.Rect(r.centerx-24, r.top-44, 48, 44)
        pg.draw.ellipse(surf, pg.Color(0,0,0), head.inflate(8,8))
        pg.draw.ellipse(surf, self.color, head)
        # fists/pose per name
        if self.name == 'TANK':
            # beard & tattoos
            pg.draw.rect(surf, pg.Color(70,40,25), (head.centerx-20, head.bottom-18, 40, 16))
            for i in range(-24, 28, 12):
                pg.draw.circle(surf, pg.Color(60,40,30), (r.centerx+i, r.centery+10), 4)
        elif self.name == 'TECHNICUS':
            # glasses & mustache
            pg.draw.rect(surf, GREY, (head.centerx-18, head.centery-6, 36, 8))
            pg.draw.rect(surf, pg.Color(40,20,10), (head.centerx-14, head.bottom-16, 28, 6))
            # scissors effect on hand
            hand = (r.centerx + 28*self.facing, r.centery-10)
            Shapes.scissors(surf, hand, 0.5)
    def hitbox(self) -> pg.Rect:
        r = self.rect
        if self.state == 'attack':
            if self.name == 'TANK':
                # forward punch
                w = 60; h=30
                if self.facing == 1:
                    return pg.Rect(r.right, r.centery-20, w, h)
                return pg.Rect(r.left-w, r.centery-20, w, h)
        if self.state == 'super':
            # larger shockwave/hit
            w = 120; h = 60
            if self.facing == 1:
                return pg.Rect(r.right, r.centery-30, w, h)
            return pg.Rect(r.left-w, r.centery-30, w, h)
        return pg.Rect(0,0,0,0)

class FoamWave:
    def __init__(self, x, y, dir):
        self.x = x; self.y = y; self.dir = dir
        self.t = 0.0
        self.dead = False
    def update(self, dt):
        self.t += dt
        self.x += self.dir * 420 * dt
        if self.x < -100 or self.x > WIDTH+100 or self.t>1.5:
            self.dead = True
    def rect(self):
        return pg.Rect(int(self.x-60), int(self.y-24), 120, 48)
    def draw(self, surf: pg.Surface):
        r = self.rect()
        # foam shockwave
        for i, col in enumerate([(255,255,255,160),(230,240,255,120),(200,220,255,80)]):
            pg.draw.ellipse(surf, col, r.inflate(i*20, i*12))

class StreetBrawl(Scene):
    def __init__(self, game: 'Game'):
        super().__init__(game)
        self.timer = 99
        self.time_acc = 0
        self.p1 = Fighter('TANK', pg.Color(180,80,60), facing=1)
        self.p2 = Fighter('TECHNICUS', pg.Color(160,140,120), facing=-1)
        self.foam: list[FoamWave] = []
        self.score = 0
        self.ended = False
    def handle_event(self, e: pg.event.Event):
        if e.type == pg.KEYDOWN and self.ended:
            if e.key == pg.K_RETURN:
                self.post_score_and_exit()
    def update(self, dt: float):
        if self.ended:
            return
        self.time_acc += dt
        if self.time_acc >= 1.0:
            self.time_acc -= 1.0
            self.timer = max(0, self.timer-1)
            if self.timer == 0:
                self.finish_round(time_out=True)
        keys = pg.key.get_pressed()
        # Player 1 controls (A/D move, W jump, J attack, K super)
        self.p1.vx = 0
        if keys[pg.K_a]: self.p1.vx = -260
        if keys[pg.K_d]: self.p1.vx = 260
        if keys[pg.K_w] and self.p1.on_ground:
            self.p1.on_ground = False
            self.p1.vy = -520
        if keys[pg.K_j] and self.p1.attack_cool <= 0:
            self.p1.state='attack'; self.p1.attack_cool = 0.35
        if keys[pg.K_k] and self.p1.super >= 100 and self.p1.attack_cool <= 0:
            self.p1.state='super'; self.p1.attack_cool = 0.6; self.p1.super = 100  # stays full per spec
            # create foam shockwave
            origin = self.p1.rect.centerx + self.p1.facing*40
            self.foam.append(FoamWave(origin, self.p1.rect.centery-10, self.p1.facing))
        # Simple AI for P2: back-jump when P1 super/attack near
        dist = abs(self.p2.x - self.p1.x)
        self.p2.vx = -160 if self.p2.facing==-1 else 160
        if dist < 200 and self.p2.on_ground:
            self.p2.on_ground=False; self.p2.vy = -480
        # Update fighters
        self.p1.update(dt); self.p2.update(dt)
        # Face each other
        self.p1.facing = 1 if self.p2.x > self.p1.x else -1
        self.p2.facing = 1 if self.p1.x > self.p2.x else -1
        # Resolve hits
        hit1 = self.p1.hitbox()
        if hit1.w>0 and hit1.colliderect(self.p2.rect) and self.p1.attack_cool>0:
            dmg = 60 if self.p1.state=='attack' else 150
            self.p2.health -= dmg
            self.p2.hurt_cool = 0.2
            self.score += dmg
            if self.p2.health <= 0:
                self.finish_round()
        # Foam waves
        for w in self.foam:
            w.update(dt)
            if w.rect().colliderect(self.p2.rect):
                self.p2.health -= 80
                self.score += 80
                w.dead = True
                if self.p2.health <= 0:
                    self.finish_round()
        self.foam = [w for w in self.foam if not w.dead]
    def finish_round(self, time_out: bool=False):
        self.ended = True
        # scoring: time bonus + remaining P1 health
        bonus = self.timer*10 + self.p1.health
        self.score += bonus
    def draw(self, surf: pg.Surface):
        draw_barbershop_bg(surf)
        # stage floor line
        pg.draw.line(surf, pg.Color(40,40,40), (0, int(HEIGHT*0.7)+40), (WIDTH, int(HEIGHT*0.7)+40), 4)
        # fighters
        self.p1.draw(surf); self.p2.draw(surf)
        # foam
        for w in self.foam: w.draw(surf)
        # UI: health bars, portraits, timer, super meters
        draw_health_bar(surf, 100, 16, 420, 24, self.p1.health, 1000, "TANK", pg.Color(180,80,60))
        draw_health_bar(surf, WIDTH-100-420, 16, 420, 24, self.p2.health, 1000, "TECHNICUS", pg.Color(160,140,120))
        draw_timer(surf, self.timer)
        draw_super_meter(surf, 100, 50, 420, 14, self.p1.super, 100)
        draw_super_meter(surf, WIDTH-100-420, 50, 420, 14, 100, 100)  # full/glow for P2 too
        if self.ended:
            dim = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA); dim.fill((0,0,0,180)); surf.blit(dim, (0,0))
            draw_outlined_text(surf, "KO!", (WIDTH//2, HEIGHT//2-80), NEON_RED, size=72, center=True)
            draw_outlined_text(surf, f"SCORE: {self.score}", (WIDTH//2, HEIGHT//2-20), WHITE, size=36, center=True)
            if self.game.scores.qualifies("street_brawl", self.score):
                draw_outlined_text(surf, "ENTER = Naam invoeren", (WIDTH//2, HEIGHT//2+40), WHITE, size=24, center=True)
            else:
                draw_outlined_text(surf, "ENTER = Terug naar menu", (WIDTH//2, HEIGHT//2+40), WHITE, size=24, center=True)
    def post_score_and_exit(self):
        if self.game.scores.qualifies("street_brawl", self.score):
            self.game.change_scene(NameEntry(self.game, board="street_brawl", score=self.score, on_done=lambda: self.game.change_scene(HighScoreBoard(self.game, "street_brawl"))))
        else:
            self.game.change_scene(Menu(self.game))

# Name entry and highscore board
class NameEntry(Scene):
    def __init__(self, game: 'Game', board: str, score: int, on_done: Optional[Callable]=None):
        super().__init__(game)
        self.board = board
        self.score = score
        self.name = ""
        self.on_done = on_done
    def handle_event(self, e: pg.event.Event):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_RETURN:
                if self.name.strip():
                    self.game.scores.add_score(self.board, self.name.strip(), self.score)
                    if self.on_done: self.on_done()
                    else: self.game.change_scene(Menu(self.game))
            elif e.key == pg.K_BACKSPACE:
                self.name = self.name[:-1]
            else:
                ch = e.unicode
                if ch and (ch.isalnum() or ch in " _-.") and len(self.name) < 16:
                    self.name += ch
    def draw(self, surf: pg.Surface):
        surf.fill(BLACK)
        draw_neon_text(surf, "HIGH SCORE", (WIDTH//2, 120), ELECTRIC_BLUE, 56)
        draw_outlined_text(surf, f"Mode: {self.board.replace('_',' ').title()}", (WIDTH//2, 200), WHITE, size=24, center=True)
        draw_outlined_text(surf, f"Score: {self.score}", (WIDTH//2, 240), WHITE, size=24, center=True)
        draw_outlined_text(surf, "Voer je naam in:", (WIDTH//2, 320), WHITE, size=28, center=True)
        draw_outlined_text(surf, self.name + ("_" if int(pg.time.get_ticks()/400)%2==0 else ""), (WIDTH//2, 370), ELECTRIC_BLUE, size=32, center=True)
        draw_outlined_text(surf, "ENTER = Opslaan", (WIDTH//2, 440), WHITE, size=22, center=True)

class HighScoreBoard(Scene):
    def __init__(self, game: 'Game', board: str):
        super().__init__(game)
        self.board = board
        self.t = 0.0
    def handle_event(self, e: pg.event.Event):
        if e.type == pg.KEYDOWN:
            self.game.change_scene(Menu(self.game))
        if e.type == pg.MOUSEBUTTONDOWN:
            self.game.change_scene(Menu(self.game))
    def update(self, dt: float):
        self.t += dt
    def draw(self, surf: pg.Surface):
        surf.fill(BLACK)
        draw_neon_text(surf, "TOP 10", (WIDTH//2, 90), NEON_RED, 60)
        draw_outlined_text(surf, f"{self.board.replace('_',' ').title()}", (WIDTH//2, 150), WHITE, size=26, center=True)
        entries = self.game.scores.data.get(self.board, [])
        y = 210
        if not entries:
            draw_outlined_text(surf, "Nog geen scores", (WIDTH//2, y), WHITE, size=24, center=True)
        else:
            for i, item in enumerate(entries, start=1):
                draw_outlined_text(surf, f"{i:2d}. {item['name']:<16} {item['score']:>6}", (WIDTH//2, y), ELECTRIC_BLUE if i==1 else WHITE, size=24, center=True)
                y += 34
        draw_outlined_text(surf, "Druk een toets om terug te gaan", (WIDTH//2, HEIGHT-40), WHITE, size=20, center=True)

# Game application
class Game:
    def __init__(self):
        pg.init()
        pg.display.set_caption(TITLE)
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        self.clock = pg.time.Clock()
        self.scene: Scene = Menu(self)
        self.scores = HighScores(SAVE_FILE)
    def change_scene(self, scene: Scene):
        self.scene = scene
        self.scene.start()
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pg.event.get():
                if e.type == pg.QUIT:
                    running = False
                elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                    # ESC vanuit games: terug naar menu
                    if isinstance(self.scene, Menu):
                        running = False
                    else:
                        self.change_scene(Menu(self))
                else:
                    self.scene.handle_event(e)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pg.display.flip()
        pg.quit()

if __name__ == '__main__':
    try:
        Game().run()
    except Exception as ex:
        print("Error:", ex)
        raise
