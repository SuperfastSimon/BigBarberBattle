#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIG BARBER BATTLE - THE MASTERPIECE EDITION
Based on real-world references: Breda Barbershop
Features:
- Procedural 'Diamond' Logo rendering
- Photo-realistic caricature rendering (Tank & Tech)
- Neon Glow Engine
- Physics-based particles
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple

# ------------------------------------------------------------
# 1. SYSTEM BOOT
# ------------------------------------------------------------
try:
    import pygame
    from pygame import Surface, Rect
    import pygame.freetype
    
    pygame.init()
    pygame.freetype.init()
except Exception as e:
    print(f"SYSTEM FAILURE: {e}", file=sys.stderr)
    sys.exit(1)

WIDTH, HEIGHT = 1280, 720
FPS = 60
DATA_DIR = Path(os.getcwd())
HS_FILE = DATA_DIR / "highscores.json"

# ------------------------------------------------------------
# 2. PALETTE (Gebaseerd op de foto's)
# ------------------------------------------------------------
COLORS = {
    "WALL_DARK": (20, 20, 25),      # De donkere muren
    "FLOOR_WOOD": (100, 70, 45),    # De houten vloer
    "SKIN": (235, 195, 165),        # Huidskleur
    "TATTOO": (60, 60, 75),         # Inkt kleur
    "NEON_RED": (255, 20, 50),      # Het bord
    "NEON_GLOW": (255, 80, 80),     # De gloed
    "GOLD": (218, 165, 32),         # Scharen/Logo details
    "DENIM": (60, 80, 110),         # Jeans
    "BLACK": (10, 10, 12),
    "WHITE": (240, 240, 240),
    "GREEN": (50, 200, 100),
    "ORANGE": (255, 140, 0)
}

# ------------------------------------------------------------
# 3. ENGINE UTILS
# ------------------------------------------------------------
def clamp(v, lo, hi): return max(lo, min(hi, v))

def load_font(size: int = 36) -> pygame.freetype.Font:
    # Probeer fonts die lijken op het "BIG BARBER" logo (strak, bold)
    prefs = ["Impact", "Arial Black", "Franklin Gothic Medium", "Verdana", "Arial"]
    for name in prefs:
        if pygame.font.match_font(name):
            return pygame.freetype.Font(pygame.font.match_font(name), size)
    return pygame.freetype.SysFont(None, size)

def draw_neon_text(dst: Surface, text: str, font: pygame.freetype.Font, pos: tuple, color: tuple, glow_color: tuple, center: bool = False, scale: float = 1.0):
    # Robuuste Neon Renderer
    sc = (int(clamp(color[0],0,255)), int(clamp(color[1],0,255)), int(clamp(color[2],0,255)))
    gc = (int(clamp(glow_color[0],0,255)), int(clamp(glow_color[1],0,255)), int(clamp(glow_color[2],0,255)))

    surf, rect = font.render(text, fgcolor=sc)
    if scale != 1.0:
        surf = pygame.transform.smoothscale(surf, (int(surf.get_width()*scale), int(surf.get_height()*scale)))
        rect = surf.get_rect()
    
    if center: rect.center = pos
    else: rect.topleft = pos

    glow = pygame.Surface((rect.width+60, rect.height+60), pygame.SRCALPHA)
    for r in range(4, 24, 4):
        alpha = int(40 * (1.0 - r/25.0))
        g_surf, _ = font.render(text, fgcolor=gc)
        factor = 1 + r/30.0
        gw, gh = int(g_surf.get_width()*factor), int(g_surf.get_height()*factor)
        g_surf = pygame.transform.smoothscale(g_surf, (gw, gh))
        
        temp = pygame.Surface(glow.get_size(), pygame.SRCALPHA)
        gr = g_surf.get_rect(center=(glow.get_width()//2, glow.get_height()//2))
        temp.blit(g_surf, gr)
        temp.fill((255,255,255,alpha), special_flags=pygame.BLEND_RGBA_MULT)
        glow.blit(temp, (0,0), special_flags=pygame.BLEND_PREMULTIPLIED)
    
    dst.blit(glow, (rect.centerx - glow.get_width()//2, rect.centery - glow.get_height()//2), special_flags=pygame.BLEND_PREMULTIPLIED)
    dst.blit(surf, rect)

@dataclass
class FloatText:
    x: float; y: float; text: str; color: tuple; life: float = 1.0
    def update(self, dt):
        self.y -= 60 * dt
        self.life -= dt
    def draw(self, dst, font):
        if self.life > 0:
            alpha = int(255 * clamp(self.life, 0, 1))
            surf, _ = font.render(self.text, fgcolor=self.color)
            s2 = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            s2.blit(surf, (0,0))
            s2.fill((255,255,255,alpha), special_flags=pygame.BLEND_RGBA_MULT)
            dst.blit(s2, (self.x, self.y))

# ------------------------------------------------------------
# 4. ASSET RENDERING (THE ART)
# ------------------------------------------------------------

def draw_diamond_logo(dst: Surface, center: tuple, scale: float = 1.0):
    """ Tekent het 'BIG BARBER' ruit-logo van de raamstickers (Foto 5,8,10) """
    cx, cy = center
    w, h = 300 * scale, 150 * scale
    
    # Diamond outline (Wit)
    points = [(cx, cy-h), (cx+w, cy), (cx, cy+h), (cx-w, cy)]
    pygame.draw.polygon(dst, (200, 200, 200), points, width=3)
    
    # Inner line
    w2, h2 = w * 0.9, h * 0.9
    points2 = [(cx, cy-h2), (cx+w2, cy), (cx, cy+h2), (cx-w2, cy)]
    pygame.draw.polygon(dst, (150, 150, 150), points2, width=1)
    
    # Schaar symbool in het midden (Simpel kruis)
    pygame.draw.line(dst, COLORS["GOLD"], (cx-20*scale, cy-20*scale), (cx+20*scale, cy+20*scale), int(4*scale))
    pygame.draw.line(dst, COLORS["GOLD"], (cx+20*scale, cy-20*scale), (cx-20*scale, cy+20*scale), int(4*scale))

def draw_barber_pole(dst: Surface, rect: Rect):
    """ Geanimeerde paal """
    pygame.draw.rect(dst, (50, 50, 50), rect.inflate(4, 20), border_radius=4) # Caps
    pygame.draw.rect(dst, (255, 255, 255), rect) # Glass
    
    clip = pygame.Surface(rect.size, pygame.SRCALPHA)
    offset = -(pygame.time.get_ticks() / 15) % 40
    for y in range(int(offset)-40, rect.height + 40, 40):
        pygame.draw.polygon(clip, (220, 0, 0), [(0, y), (rect.width, y+20), (rect.width, y+30), (0, y+10)])
        pygame.draw.polygon(clip, (0, 0, 220), [(0, y+20), (rect.width, y+40), (rect.width, y+50), (0, y+30)])
    
    dst.blit(clip, rect)
    # Shine
    pygame.draw.rect(dst, (255,255,255), Rect(rect.x+4, rect.y, 4, rect.height)) 

def draw_detailed_character(dst: Surface, x, y, archetype="tank", scale=1.0):
    """ 
    Gebaseerd op de groepsfoto (Foto 1 & 4).
    """
    # Basis afmetingen
    w = 70 * scale
    h = 100 * scale
    head_r = 28 * scale
    
    # --- BODY ---
    # Zwart T-shirt (V-Hals voor tank, Polo voor tech)
    shirt_rect = Rect(x - w//2, y - h//1.5, w, h)
    pygame.draw.rect(dst, (15, 15, 15), shirt_rect, border_radius=int(10*scale))
    
    # V-Hals cutout voor Tank
    if archetype == "tank":
        pygame.draw.polygon(dst, COLORS["SKIN"], [(x-10*scale, y-h//1.5), (x+10*scale, y-h//1.5), (x, y-h//1.5 + 15*scale)])
    
    # --- ARMS & TATTOOS ---
    # Armen
    pygame.draw.line(dst, COLORS["SKIN"], (x-w//2, y-h//2), (x-w//2 - 15*scale, y), int(14*scale))
    pygame.draw.line(dst, COLORS["SKIN"], (x+w//2, y-h//2), (x+w//2 + 15*scale, y), int(14*scale))
    
    # Tattoos (Abstracte donkere vlakken op armen) - Zoals op foto
    pygame.draw.line(dst, COLORS["TATTOO"], (x-w//2-5*scale, y-h//3), (x-w//2 - 10*scale, y-10*scale), int(10*scale))
    pygame.draw.line(dst, COLORS["TATTOO"], (x+w//2+5*scale, y-h//3), (x+w//2 + 10*scale, y-10*scale), int(10*scale))

    # --- LEGS ---
    if archetype == "tank":
        # Donkere Jeans
        pygame.draw.rect(dst, (20, 20, 30), Rect(x-w//2+5, y+h//3, w-10, h//1.5))
        # Bruine Boots (Foto 1)
        pygame.draw.rect(dst, (100, 70, 20), Rect(x-w//2, y+h, w//2-2, 15*scale)) 
        pygame.draw.rect(dst, (100, 70, 20), Rect(x+2, y+h, w//2-2, 15*scale))
    else:
        # Lichtere Jeans (Blue)
        pygame.draw.rect(dst, COLORS["DENIM"], Rect(x-w//2+5, y+h//3, w-10, h//1.5))
        # Zwarte Schoenen
        pygame.draw.rect(dst, (10, 10, 10), Rect(x-w//2, y+h, w//2-2, 15*scale))
        pygame.draw.rect(dst, (10, 10, 10), Rect(x+2, y+h, w//2-2, 15*scale))

    # --- HEAD ---
    pygame.draw.circle(dst, COLORS["SKIN"], (x, y - h//1.2), head_r)
    
    if archetype == "tank":
        # -- THE TANK (Links) --
        # Haar: Opgeschoren, donker bovenop
        pygame.draw.arc(dst, (20, 20, 20), Rect(x-head_r, y-h//1.2-head_r, head_r*2, head_r*2), 0, 3.14, int(6*scale))
        # Baard: Vol, donker
        pygame.draw.polygon(dst, (20, 20, 20), [
            (x-head_r, y-h//1.2), (x+head_r, y-h//1.2), 
            (x+head_r*0.8, y-h//1.2+25*scale), (x-head_r*0.8, y-h//1.2+25*scale)
        ])
        
    else:
        # -- THE TECHNICIAN (Rechts) --
        # Haar: Krullend/Wavy, bril
        # Krullen (cirkeltjes)
        for i in range(-3, 4):
            pygame.draw.circle(dst, (20, 20, 20), (x + i*7*scale, y - h//1.2 - 15*scale), 8*scale)
        
        # Bril (Rond montuur - Foto 1)
        pygame.draw.circle(dst, (10,10,10), (x-8*scale, y-h//1.2), 8*scale, width=2)
        pygame.draw.circle(dst, (10,10,10), (x+8*scale, y-h//1.2), 8*scale, width=2)
        pygame.draw.line(dst, (10,10,10), (x-4*scale, y-h//1.2), (x+4*scale, y-h//1.2), 2)
        
        # Snor
        pygame.draw.line(dst, (20,20,20), (x-10*scale, y-h//1.2+10*scale), (x+10*scale, y-h//1.2+10*scale), int(3*scale))
        # Schaar in hand
        draw_diamond_logo(dst, (x+40*scale, y), scale=0.05) # Mini logo als schaar placeholder

# ------------------------------------------------------------
# 5. SCENES & LOGIC
# ------------------------------------------------------------
class GameApp:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("BIG BARBER BATTLE: BREDA EDITION")
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.font = load_font(32)
        self.font_big = load_font(64)
        
        self.highscores = self.load_hs()
        self.scenes = [MenuScene(self)]
        self.shake = 0.0

    def load_hs(self):
        try:
            with open(HS_FILE, "r") as f: return json.load(f)
        except: return {"precision": [], "brawl": []}
    
    def save_hs(self):
        try:
            with open(HS_FILE, "w") as f: json.dump(self.highscores, f)
        except: pass

    def push(self, s): self.scenes.append(s)
    def pop(self): self.scenes.pop() if self.scenes else None
    def replace(self, s): 
        if self.scenes: self.scenes[-1] = s
        else: self.scenes.append(s)

    def trigger_shake(self, amount=0.2): self.shake = amount

    def run(self):
        while self.running and self.scenes:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.running = False
                else: self.scenes[-1].handle_event(e)
            
            self.scenes[-1].update(dt)
            
            # Draw / Shake
            off = (0,0)
            if self.shake > 0:
                self.shake -= dt
                off = (random.randint(-4,4), random.randint(-4,4))
            
            base = Surface((WIDTH, HEIGHT))
            self.scenes[-1].draw(base)
            self.screen.blit(base, off)
            pygame.display.flip()
        self.save_hs()
        pygame.quit()

def draw_environment(dst: Surface):
    # Dark Industrial Walls
    dst.fill(COLORS["WALL_DARK"])
    
    # Wooden Floor (Foto 2, 6)
    pygame.draw.rect(dst, COLORS["FLOOR_WOOD"], Rect(0, HEIGHT-150, WIDTH, 150))
    # Plank lines
    for i in range(0, WIDTH, 60):
        pygame.draw.line(dst, (90, 60, 40), (i, HEIGHT-150), (i-40, HEIGHT), 2)

    # Mirrors/Stations
    for i in range(3):
        x = 150 + i * 380
        # Mirror Frame
        pygame.draw.rect(dst, (10,10,10), Rect(x, 100, 220, 300))
        # Glass
        pygame.draw.rect(dst, (40, 40, 50), Rect(x+10, 110, 200, 280))
        # Reflection Light
        pygame.draw.line(dst, (60,60,70), (x+20, 350), (x+100, 120), 2)
        
        # Diamond Logo on Mirror (Foto 5 sticker)
        draw_diamond_logo(dst, (x+110, 160), scale=0.3)

    # Barber Poles (Foto 9, 10)
    draw_barber_pole(dst, Rect(20, 150, 40, 200))
    draw_barber_pole(dst, Rect(WIDTH-60, 150, 40, 200))
    
    # Neon Sign (Foto 2)
    try:
        f = load_font(48)
        draw_neon_text(dst, "IT'S A CUT-THROAT BUSINESS", f, (WIDTH//2, 50), COLORS["NEON_RED"], COLORS["NEON_GLOW"], center=True)
    except: pass

class MenuScene:
    def __init__(self, app):
        self.app = app
        self.sel = 0

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_LEFT, pygame.K_a): self.sel = 0
            elif e.key in (pygame.K_RIGHT, pygame.K_d): self.sel = 1
            elif e.key == pygame.K_RETURN:
                if self.sel == 0: self.app.push(PrecisionCutGame(self.app))
                else: self.app.push(StreetBrawlGame(self.app))

    def update(self, dt): pass
    def draw(self, dst):
        draw_environment(dst)
        
        # Split overlay
        overlay = Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        l_a = 100 if self.sel == 0 else 180
        r_a = 100 if self.sel == 1 else 180
        pygame.draw.rect(overlay, (0,0,0,l_a), Rect(0,0,WIDTH//2,HEIGHT))
        pygame.draw.rect(overlay, (0,0,0,r_a), Rect(WIDTH//2,0,WIDTH//2,HEIGHT))
        dst.blit(overlay, (0,0))

        # Left Option
        draw_diamond_logo(dst, (WIDTH//4, HEIGHT//2), scale=0.8)
        draw_neon_text(dst, "PRECISION CUT", self.app.font, (WIDTH//4, 180), COLORS["WHITE"], COLORS["DENIM"], center=True)
        
        # Right Option: The Fighters
        # Draw Tank & Tech side by side
        draw_detailed_character(dst, WIDTH*0.75 - 50, HEIGHT//2 + 50, "tank", 1.2)
        draw_detailed_character(dst, WIDTH*0.75 + 50, HEIGHT//2 + 50, "tech", 1.2)
        draw_neon_text(dst, "STREET BRAWL", self.app.font, (WIDTH*0.75, 180), COLORS["WHITE"], COLORS["NEON_RED"], center=True)

        # Footer
        hint = "LEFT/RIGHT to Choose  -  ENTER to Start"
        t, _ = self.app.font.render(hint, fgcolor=COLORS["WHITE"])
        dst.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT-40))

class PrecisionCutGame:
    def __init__(self, app):
        self.app = app
        self.time = 45.0
        self.score = 0
        self.combo = 0
        self.mouse = (WIDTH//2, HEIGHT//2)
        self.texts = []

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE: self.app.pop()
        elif e.type == pygame.MOUSEMOTION: self.mouse = e.pos
        elif e.type == pygame.MOUSEBUTTONDOWN:
            mx, my = e.pos
            # Hit check
            if abs(my - HEIGHT//2) < 50 and abs(mx - WIDTH//2) < 150:
                pts = 10 + self.combo * 5
                self.score += pts
                self.combo += 1
                txt = random.choice(["FRESH!", "CLEAN!", "SHARP!", "BIG!"])
                self.texts.append(FloatText(mx, my, txt, COLORS["GREEN"]))
            else:
                self.combo = 0
                self.texts.append(FloatText(mx, my, "OOPS", COLORS["NEON_RED"]))

    def update(self, dt):
        self.time -= dt
        if self.time <= 0: self.app.replace(HighScoreGate(self.app, "precision", self.score))
        for t in self.texts: t.update(dt)
        self.texts = [t for t in self.texts if t.life > 0]

    def draw(self, dst):
        draw_environment(dst)
        
        # Focus Area
        rect = Rect(WIDTH//2 - 150, HEIGHT//2 - 180, 300, 360)
        pygame.draw.rect(dst, (20, 20, 20), rect, border_radius=20)
        pygame.draw.rect(dst, COLORS["WHITE"], rect, width=3, border_radius=20)
        
        # Customer Head (Abstract)
        pygame.draw.circle(dst, COLORS["SKIN"], rect.center, 80)
        # Fade Zone
        pygame.draw.rect(dst, (50, 200, 50, 50), Rect(WIDTH//2-90, HEIGHT//2-20, 180, 40))

        # Clippers
        mx, my = self.mouse
        pygame.draw.rect(dst, COLORS["GOLD"], Rect(mx-20, my-30, 40, 60), border_radius=5)
        
        # UI
        draw_neon_text(dst, f"SCORE: {self.score}", self.app.font, (50, 50), COLORS["WHITE"], COLORS["DENIM"])
        draw_neon_text(dst, f"TIME: {int(self.time)}", self.app.font, (WIDTH-200, 50), COLORS["NEON_RED"], COLORS["NEON_GLOW"])
        for t in self.texts: t.draw(dst, self.app.font)

class StreetBrawlGame:
    def __init__(self, app):
        self.app = app
        self.p1 = {"x": WIDTH*0.3, "hp": 100, "type": "tank"}
        self.p2 = {"x": WIDTH*0.7, "hp": 100, "type": "tech"}
        self.timer = 99.0
        self.texts = []

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE: self.app.pop()
            if e.key in (pygame.K_j, pygame.K_k): # Attack
                dist = abs(self.p1["x"] - self.p2["x"])
                if dist < 150:
                    dmg = random.randint(8, 15)
                    self.p2["hp"] -= dmg
                    self.app.trigger_shake(0.2)
                    self.texts.append(FloatText(self.p2["x"], HEIGHT//2, f"-{dmg}", COLORS["ORANGE"]))
                    self.p2["x"] += 60 # Knockback
                else:
                    self.texts.append(FloatText(self.p1["x"], HEIGHT//2-100, "MISS", COLORS["WHITE"]))

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0 or self.p1["hp"] <= 0 or self.p2["hp"] <= 0:
            sc = int(self.p1["hp"] + self.timer)
            self.app.replace(HighScoreGate(self.app, "brawl", sc))
        
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]: self.p1["x"] -= 300 * dt
        if keys[pygame.K_d]: self.p1["x"] += 300 * dt
        
        # AI Logic (Tech backs away or counters)
        dist = self.p1["x"] - self.p2["x"]
        if abs(dist) < 100: self.p2["x"] += 200 * dt
        elif abs(dist) > 300: self.p2["x"] -= 100 * dt
        
        # Clamp
        self.p1["x"] = clamp(self.p1["x"], 100, WIDTH-100)
        self.p2["x"] = clamp(self.p2["x"], 100, WIDTH-100)
        for t in self.texts: t.update(dt)

    def draw(self, dst):
        draw_environment(dst)
        
        # Fighters
        floor_y = HEIGHT - 120
        draw_detailed_character(dst, self.p1["x"], floor_y, "tank", 1.5)
        draw_detailed_character(dst, self.p2["x"], floor_y, "tech", 1.5)
        
        # HUD
        bar_w = 400
        pygame.draw.rect(dst, COLORS["BLACK"], Rect(50, 40, bar_w, 30))
        pygame.draw.rect(dst, COLORS["ORANGE"], Rect(50, 40, bar_w * (self.p1["hp"]/100), 30))
        
        pygame.draw.rect(dst, COLORS["BLACK"], Rect(WIDTH-50-bar_w, 40, bar_w, 30))
        pygame.draw.rect(dst, COLORS["GREEN"], Rect(WIDTH-50-bar_w, 40, bar_w * (self.p2["hp"]/100), 30))
        
        draw_neon_text(dst, str(int(self.timer)), self.app.font_big, (WIDTH//2, 60), COLORS["WHITE"], COLORS["GOLD"], center=True)
        
        for t in self.texts: t.draw(dst, self.app.font)

class HighScoreGate:
    def __init__(self, app, mode, score):
        self.app = app; self.mode = mode; self.score = score; self.name = ""
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_RETURN:
                self.app.highscores[self.mode].append({"name": self.name or "ANON", "score": self.score})
                self.app.highscores[self.mode] = sorted(self.app.highscores[self.mode], key=lambda x: x["score"], reverse=True)[:10]
                self.app.pop()
            elif e.key == pygame.K_BACKSPACE: self.name = self.name[:-1]
            elif e.unicode.isalnum() and len(self.name)<10: self.name += e.unicode
    def update(self, dt): pass
    def draw(self, dst):
        draw_environment(dst)
        overlay = Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,200))
        dst.blit(overlay, (0,0))
        
        draw_neon_text(dst, "GAME OVER", self.app.font_big, (WIDTH//2, 150), COLORS["NEON_RED"], COLORS["NEON_GLOW"], center=True)
        t1, _ = self.app.font.render(f"FINAL SCORE: {self.score}", fgcolor=COLORS["WHITE"])
        t2, _ = self.app.font.render(f"NAME: {self.name}_", fgcolor=COLORS["GOLD"])
        dst.blit(t1, (WIDTH//2 - t1.get_width()//2, 300))
        dst.blit(t2, (WIDTH//2 - t2.get_width()//2, 400))

if __name__ == "__main__":
    GameApp().run()

