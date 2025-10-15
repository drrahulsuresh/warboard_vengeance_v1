#!/usr/bin/env python3
# WarBoard: Vengeance (v1)
#
# Notes:
# - Missile launching: select missile -> click your tile (launch) -> click enemy tile (target).
# - To place purchased units mid-battle: press 1/2/3/5/6 and click your side (uses your one move).

import os, sys, json, random, math
import pygame

WIDTH, HEIGHT   = 1200, 720
FPS             = 60
GRID_W, GRID_H  = 28, 13
TILE            = 38
MARGIN_X        = 40
MARGIN_Y        = 40
PANEL_H         = 180
KM_PER_TILE     = 100

AA_RANGE_BASE    = 4
RADAR_RANGE_BASE = 4

WHITE=(255,255,255); LIGHTGRAY=(185,190,200); GREEN=(60,200,90)
YELLOW=(240,220,80); ORANGE=(240,170,60); BLUE=(80,120,240); CYAN=(80,220,220)
DARK=(22,26,34); PANEL_BG=(26,28,36)

def resource_path(rel_path:str)->str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)

pygame.init()
FONT_XL= pygame.font.SysFont("arial", 48, bold=True)
FONT_L = pygame.font.SysFont("arial", 28)
FONT   = pygame.font.SysFont("arial", 20)
FONT_S = pygame.font.SysFont("arial", 16)
FONT_XS= pygame.font.SysFont("arial", 14)

def biased_center_x(bias_ratio=0.08):
    return int(WIDTH//2 - WIDTH*bias_ratio)

class Button:
    def __init__(self, rect, text, onclick=None):
        self.rect = pygame.Rect(rect); self.text=text; self.onclick=onclick; self.hover=False
    def draw(self, surf):
        col = (80,130,220) if self.hover else (55,95,170)
        pygame.draw.rect(surf, col, self.rect, border_radius=10)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=10)
        r = FONT.render(self.text, True, WHITE)
        surf.blit(r, r.get_rect(center=self.rect.center))
    def handle(self, event):
        if event.type==pygame.MOUSEMOTION: self.hover = self.rect.collidepoint(event.pos)
        elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and self.rect.collidepoint(event.pos):
            if self.onclick: self.onclick()

class Dropdown:
    def __init__(self, rect, options, selected=None):
        self.rect=pygame.Rect(rect); self.options=options[:]; self.open=False
        if options:
            self.selected=selected if selected in options else options[0]
        else:
            self.selected=None
        self.scroll=0; self.max_visible=10; self.item_h=self.rect.height
    def draw(self, surf):
        pygame.draw.rect(surf, (50,50,50), self.rect, border_radius=8)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=8)
        label = str(self.selected) if self.selected is not None else "—"
        surf.blit(FONT.render(label, True, WHITE), (self.rect.x+8, self.rect.y+8))
        pygame.draw.polygon(surf, WHITE, [(self.rect.right-20, self.rect.centery-4),(self.rect.right-8,self.rect.centery-4),(self.rect.right-14,self.rect.centery+6)])
    def draw_list(self, surf):
        if not self.open: return None
        max_h = self.max_visible*self.item_h
        list_rect = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, max_h)
        pygame.draw.rect(surf, (30,30,30), list_rect, border_radius=6)
        pygame.draw.rect(surf, WHITE, list_rect, 2, border_radius=6)
        start=self.scroll; end=min(len(self.options), start+self.max_visible)
        for i,opt in enumerate(self.options[start:end], start):
            r = pygame.Rect(self.rect.x, self.rect.bottom+(i-start)*self.item_h, self.rect.width, self.item_h)
            hov = r.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(surf, (60,60,60) if hov else (40,40,40), r)
            pygame.draw.rect(surf, WHITE, r, 1)
            pygame.draw.rect(surf, (100,100,100), (r.right-20, r.y+6, 1, r.height-12))
            surf.blit(FONT_S.render(str(opt), True, WHITE), (r.x+8, r.y+8))
        return list_rect
    def handle(self, event):
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if self.rect.collidepoint(event.pos): self.open = not self.open
            elif self.open:
                max_h=self.max_visible*self.item_h; list_rect=pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, max_h)
                if list_rect.collidepoint(event.pos):
                    idx=(event.pos[1]-self.rect.bottom)//self.item_h + self.scroll
                    if 0<=idx<len(self.options): self.selected=self.options[idx]; self.open=False
                else: self.open=False
        elif event.type==pygame.MOUSEWHEEL and self.open:
            if event.y<0 and self.scroll < max(0, len(self.options)-self.max_visible): self.scroll+=1
            elif event.y>0 and self.scroll>0: self.scroll-=1

def load_countries():
    with open(resource_path("data/countries.json"), "r", encoding="utf-8") as f:
        return json.load(f)
COUNTRIES = load_countries()

class Missile:
    def __init__(self, name, range_km, dmg=25, radius_tiles=1, anti_radar=False):
        self.name=name; self.range_km=range_km; self.damage=dmg; self.radius_tiles=radius_tiles; self.anti_radar=anti_radar

UNIT_META = {
    "Tank":  {"power":3, "color_p":(240,170,60), "color_e":(240,90,90),  "speed":18, "range":4},
    "Troop": {"power":1, "color_p":(60,200,90),  "color_e":(255,120,120), "speed":26, "range":2},
    "Jet":   {"power":4, "color_p":(240,220,80), "color_e":(255,180,120), "speed":10, "range":6},
}

def draw_tank_icon(surf, x,y, dir, col):
    pygame.draw.rect(surf, col, (x+8,y+18,24,14), 2)
    pygame.draw.circle(surf, col, (x+20,y+22), 6, 2)
    pygame.draw.line(surf, col, (x+20,y+22), (x+20+12*dir,y+22), 2)

def draw_troop_icon(surf, x,y, dir, col):
    pygame.draw.circle(surf, col, (x+20,y+16), 5, 2)
    pygame.draw.line(surf, col, (x+20,y+20), (x+20,y+30), 2)
    pygame.draw.line(surf, col, (x+12,y+24), (x+28,y+24), 2)
    pygame.draw.line(surf, col, (x+20,y+30), (x+20+8*dir,y+36), 2)
    pygame.draw.line(surf, col, (x+20,y+30), (x+20-8*dir,y+36), 2)

def draw_jet_icon(surf, x,y, dir, col):
    pts=[(x+20, y+10), (x+10, y+30), (x+30, y+30)]
    if dir<0: pts=[(x+20, y+30), (x+10, y+10), (x+30, y+10)]
    pygame.draw.polygon(surf, col, pts, 2)
    pygame.draw.line(surf, col, (x+20,y+20), (x+20+8*dir,y+26), 2)

def draw_unit_icon(surf, t, gx,gy, dir, enemy=False):
    x,y = MARGIN_X+gx*TILE, MARGIN_Y+gy*TILE
    col = UNIT_META[t]["color_e" if enemy else "color_p"]
    if t=="Tank":  draw_tank_icon(surf,x,y,dir,col)
    elif t=="Troop": draw_troop_icon(surf,x,y,dir,col)
    elif t=="Jet":   draw_jet_icon(surf,x,y,dir,col)

def draw_radar(surf, x,y):
    pygame.draw.circle(surf, (160,220,140), (x+TILE//2,y+TILE//2), 10, 2)
    pygame.draw.circle(surf, (160,220,140), (x+TILE//2,y+TILE//2), 5, 1)
    txt = FONT_XS.render("RDR", True, (160,220,140))
    surf.blit(txt, (x+TILE//2-12, y+TILE//2-22))

def draw_missile_sprite(surf, px,py, dir):
    body = [(px,py-6),(px+10*dir,py),(px,py+6)]
    pygame.draw.polygon(surf, WHITE, body, 2)
    pygame.draw.circle(surf, (255,180,80), (int(px-6*dir), py), 3)

class PlayerSide:
    def __init__(self, country_name, is_human=True):
        self.name=country_name; self.data=COUNTRIES[country_name]; self.is_human=is_human
        self.damage=0; self.static=[]; self.facilities=[]
        # Country missiles + default AR missile
        self.missiles=[Missile(m['name'], m['range_km'], m.get('damage',25), m.get('radius',1)) for m in self.data["missiles"]]
        self.missiles.append(Missile("AR Missile", 700, 12, 1, anti_radar=True))
        self.shots_left=1
        g,a=self.data["ground"], self.data["air"]
        self.tank_tokens = max(0,min(3, g["tanks"]//3000))
        self.troop_tokens= max(1,min(4, g["personnel"]//500000))
        self.jet_tokens  = max(1,min(3, a["fighters"]//400))
        self.aa_tokens   = max(1, int(self.data["defense"].get("air_defense",0.4)*4))
        self.radar_tokens= 1
        self.units=[]; self.orders=[]
        self.money=120; self.tokens=0
        self.aa_range_bonus=0
        self.radar_range_bonus=0
        self.intercept_cash_bonus=0

    def mobile_at(self,gx,gy): 
        for i,(t,(ux,uy),d) in enumerate(self.units):
            if (ux,uy)==(gx,gy): return i,t
        return None,None
    def static_at(self,gx,gy):
        for i,(t,(ux,uy)) in enumerate(self.static):
            if (ux,uy)==(gx,gy): return i,t
        return None,None
    def has_static_at(self,gx,gy): return any((ux==gx and uy==gy) for t,(ux,uy) in self.static)

class Board:
    def __init__(self):
        self.grid_rect=pygame.Rect(MARGIN_X,MARGIN_Y,GRID_W*TILE,GRID_H*TILE)
        self.mid_x=GRID_W//2
    def draw(self, surf):
        surf.fill(DARK)
        for gx in range(GRID_W):
            for gy in range(GRID_H):
                x=MARGIN_X+gx*TILE; y=MARGIN_Y+gy*TILE
                rect=pygame.Rect(x,y,TILE,TILE)
                col=(33,40,50) if gx<self.mid_x else (35,34,46)
                pygame.draw.rect(surf,col,rect); pygame.draw.rect(surf,(52,60,75),rect,1)
        xmid=MARGIN_X+self.mid_x*TILE
        pygame.draw.line(surf,(200,200,200),(xmid,MARGIN_Y),(xmid,MARGIN_Y+GRID_H*TILE),2)
        cy=MARGIN_Y+GRID_H*TILE//2
        pygame.draw.polygon(surf,(200,200,200),[(MARGIN_X-24,cy),(MARGIN_X-6,cy-10),(MARGIN_X-6,cy+10)])
        pygame.draw.polygon(surf,(200,200,200),[(MARGIN_X+GRID_W*TILE+24,cy),(MARGIN_X+GRID_W*TILE+6,cy-10),(MARGIN_X+GRID_W*TILE+6,cy+10)])
        surf.blit(FONT_S.render("AI ◄", True, WHITE),(MARGIN_X-58, cy-8))
        surf.blit(FONT_S.render("► YOU", True, WHITE),(MARGIN_X+GRID_W*TILE+6, cy-8))
        pygame.draw.rect(surf, PANEL_BG, (0, HEIGHT-PANEL_H, WIDTH, PANEL_H))
        pygame.draw.line(surf, (80,90,110), (0, HEIGHT-PANEL_H), (WIDTH, HEIGHT-PANEL_H), 2)
    def grid_at_pixel(self,pos):
        x,y=pos
        if not self.grid_rect.collidepoint(x,y): return None
        return (x-MARGIN_X)//TILE, (y-MARGIN_Y)//TILE
    def pixel_of_grid(self,gx,gy): return MARGIN_X+gx*TILE, MARGIN_Y+gy*TILE

class Explosion:
    def __init__(self, center_px, life=24):
        self.cx,self.cy=center_px; self.life=life; self.max_life=life
    def draw(self, surf):
        t=1.0-self.life/self.max_life; r=int(10+36*t)
        s=pygame.Surface((r*2,r*2), pygame.SRCALPHA)
        pygame.draw.circle(s,(255,150,0,int(220*(1-t))),(r,r), r)
        pygame.draw.circle(s,(255,240,180,int(240*(1-t))),(r,r), max(1,r//2))
        surf.blit(s,(self.cx-r,self.cy-r)); self.life -= 1

def highlight_range(surf, origin, rng, board, color=(160,160,160)):
    ox,oy=origin
    for gx in range(max(0,ox-rng), min(GRID_W,ox+rng+1)):
        for gy in range(max(0,oy-rng), min(GRID_H,oy+rng+1)):
            if abs(gx-ox)+abs(gy-oy)<=rng:
                x,y=board.pixel_of_grid(gx,gy)
                pygame.draw.rect(surf,color,(x+4,y+4,TILE-8,TILE-8),1)

def draw_static_defenses(surf, side, reveal_set=None, is_enemy=False, board=None):
    for t,(gx,gy) in side.static:
        if is_enemy and reveal_set is not None and (gx,gy) not in reveal_set: continue
        x,y=board.pixel_of_grid(gx,gy)
        if t=="AA":
            pygame.draw.circle(surf, CYAN, (x+TILE//2,y+TILE//2), 10, 2)
            surf.blit(FONT_XS.render("AA", True, CYAN),(x+TILE//2-10,y+TILE//2-24))
        elif t=="Radar":
            draw_radar(surf,x,y)

def draw_units_for_side(surf, side, reveal_set=None, is_enemy=False, board=None):
    for t,(gx,gy),d in side.units:
        if is_enemy and reveal_set is not None and (gx,gy) not in reveal_set: continue
        draw_unit_icon(surf, t, gx,gy, d, enemy=is_enemy)

STATE_MENU="menu"; STATE_SELECT="select"; STATE_DEPLOY="deploy"; STATE_PLAYER="player"
STATE_ANIM_MISSILE="anim_missile"; STATE_ANIM_MOVES="anim_moves"; STATE_GAME_OVER="game_over"

class Game:
    def __init__(self):
        self.screen=pygame.display.set_mode((WIDTH,HEIGHT)); pygame.display.set_caption("WarBoard: Vengeance")
        self.clock=pygame.time.Clock(); self.board=Board()
        self.state=STATE_MENU; self.info=""; self.flash_timer=0
        cx = biased_center_x(0.08)
        self.btn_start=Button((cx-90, HEIGHT//2, 180, 48),"Start", lambda:self.goto(STATE_SELECT))
        self.btn_help=Button((cx-110, HEIGHT//2+64, 220, 44),"How to Play", self.toggle_help)
        opts=list(COUNTRIES.keys())
        dd_y = 130
        def _opt(idx, fallback):
            return opts[idx] if len(opts)>idx else (opts[0] if opts else fallback)
        self.dd_p1=Dropdown((WIDTH//2-300, dd_y, 280, 40),opts,selected=_opt(0,None))
        self.dd_p2=Dropdown((WIDTH//2+20,  dd_y, 280, 40),opts,selected=_opt(1,_opt(0,None)))
        self.btn_confirm=Button((WIDTH//2-80, dd_y+60, 160, 40),"Confirm", self.confirm_countries)
        self.btn_main_menu_br=Button((WIDTH-180, HEIGHT-60, 160, 44),"Main Menu", lambda:self.reset_to_menu())
        self.btn_market=Button((MARGIN_X,20,140,40),"Market", self.toggle_market)
        self.btn_start_battle=Button((MARGIN_X+160,20,160,40),"Start Battle", self.finish_deploy)

        self.p1=self.p2=None
        self.selected_missile=None; self.range_center=None
        self.selected_unit_idx=None
        self.explosions=[]; self.destroyed_tiles=set()
        self.help_open=False; self.market_open=False
        self.help_text=(
            "• Choose both countries, place units with 1/2/3/5/6, then Start Battle."
            "• Right-click on your half to retract during Deploy (disabled after battle starts)."
            "• Your turn: Move ONE unit OR fire ONE missile. Placing a new unit mid-battle also uses your turn."
            "• Radar reveals enemies; AA intercepts missiles and jets inside radar coverage."
            "• Market is available anytime. Close with X / ESC / outside click."
        )
        self.revealed_p1=set(); self.revealed_p2=set()
        self.radar_cover_p1=set(); self.radar_cover_p2=set()
        self.radar_flash_timer=0
        self.anim={"missile":None,"moves":None,"intercept":None}
        self.move_snapshot={"p1":None,"p2":None}
        self.moves_left=1; self.deploy_choice=None
        self.market_items=self.build_market()
        self.market_rect=None
        self.game_over_timer=0

    def wrap_text(self,text,max_chars=96):
        words=text.split(); lines=[]; cur=""
        for w in words:
            if len(cur)+len(w)+(1 if cur else 0) > max_chars:
                if cur: lines.append(cur); cur=w
                else: lines.append(w)
            else:
                cur = (cur+" "+w).strip() if cur else w
        if cur: lines.append(cur)
        return lines

    def reset_to_menu(self):
        self.p1=self.p2=None
        self.selected_missile=None; self.range_center=None; self.selected_unit_idx=None
        self.revealed_p1.clear(); self.revealed_p2.clear()
        self.radar_cover_p1.clear(); self.radar_cover_p2.clear()
        self.explosions.clear(); self.destroyed_tiles.clear()
        self.market_open=False; self.help_open=False; self.info=""
        self.moves_left=1; self.deploy_choice=None
        self.state=STATE_MENU
        opts=list(COUNTRIES.keys())
        dd_y = 130
        def _opt(idx, fallback):
            return opts[idx] if len(opts)>idx else (opts[0] if opts else fallback)
        self.dd_p1=Dropdown((WIDTH//2-300, dd_y, 280, 40),opts,selected=_opt(0,None))
        self.dd_p2=Dropdown((WIDTH//2+20,  dd_y, 280, 40),opts,selected=_opt(1,_opt(0,None)))

    def goto(self, st):
        self.state=st; self.info=""; self.flash_timer=0
        if st!=STATE_MENU: self.help_open=False
        self.selected_unit_idx=None; self.selected_missile=None; self.range_center=None
        if st==STATE_PLAYER and self.p1:
            self.moves_left=1
            self.p1.shots_left=1
        if st==STATE_GAME_OVER:
            self.game_over_timer = FPS*3

    def toggle_help(self): 
        if self.state==STATE_MENU: self.help_open=not self.help_open

    def toggle_market(self): self.market_open=not self.market_open

    def build_market(self):
        items=[
            {"name":"Tank","price":90},
            {"name":"Troop","price":40},
            {"name":"Jet","price":140},
            {"name":"AA Battery","price":70, "grant":"AA"},
            {"name":"Radar Station","price":80, "grant":"Radar"},
            {"name":"Anti-Radar Missile (ARM)","price":130, "missile":("ARM", 800, 14, 1), "anti":True},
            {"name":"Anti-Radar (AR) Missile","price":110, "missile":("AR Missile", 700, 12, 1), "anti":True},
            {"name":"Akash Battery (India)","price":85, "grant":"AA", "perk":"akash"},
            {"name":"S-400 Battery (Russia)","price":120, "grant":"AA", "perk":"s400"},
            {"name":"Patriot PAC-3 (USA)","price":115, "grant":"AA", "perk":"patriot"},
            {"name":"Iron Dome Launcher (Israel)","price":95, "grant":"AA", "perk":"irondome"},
        ]
        seen=set()
        for cname, c in COUNTRIES.items():
            for m in c["missiles"]:
                key=(m["name"], m["range_km"], m.get("damage",25), m.get("radius",1))
                if key in seen: continue
                seen.add(key)
                price = int(0.02*m["range_km"] + 3.0*m.get("damage",25) + 16*m.get("radius",1))
                items.append({"name":f"{m['name']} ({cname})","price":price,
                              "missile":(m["name"], m["range_km"], m.get("damage",25), m.get("radius",1))})
        return items

    def confirm_countries(self):
        if not (self.dd_p1.selected and self.dd_p2.selected):
            self.info="Select both countries."; self.flash_timer=60; return
        if self.dd_p1.selected==self.dd_p2.selected:
            self.info="Pick two different countries."; self.flash_timer=60; return
        self.p1=PlayerSide(self.dd_p1.selected, True); self.p2=PlayerSide(self.dd_p2.selected, False)
        self.place_facilities(self.p1, True); self.place_facilities(self.p2, False)
        used=set()
        for _ in range(self.p2.tank_tokens):
            gx,gy=self.rand_tile(ai=True, used=used); self.p2.units.append(('Tank',(gx,gy),-1)); used.add((gx,gy))
        for _ in range(self.p2.troop_tokens):
            gx,gy=self.rand_tile(ai=True, used=used); self.p2.units.append(('Troop',(gx,gy),-1)); used.add((gx,gy))
        for _ in range(self.p2.jet_tokens):
            gx,gy=self.rand_tile(ai=True, used=used); self.p2.units.append(('Jet',(gx,gy),-1)); used.add((gx,gy))
        radar_spots=[]
        for _ in range(max(1,self.p2.radar_tokens)):
            rx=random.randint(self.board.mid_x+1, min(GRID_W-1, self.board.mid_x+4))
            ry=random.randrange(GRID_H)
            while (rx,ry) in used: ry=(ry+1)%GRID_H
            used.add((rx,ry)); self.p2.static.append(("Radar",(rx,ry))); radar_spots.append((rx,ry))
        for _ in range(max(1,self.p2.aa_tokens//2)):
            if radar_spots:
                brx,bry=random.choice(radar_spots)
                ax=max(self.board.mid_x+1, min(GRID_W-1, brx + random.randint(-2,2)))
                ay=max(0, min(GRID_H-1, bry + random.randint(-2,2)))
            else:
                ax=random.randint(self.board.mid_x+1, GRID_W-1); ay=random.randrange(GRID_H)
            while (ax,ay) in used: ay=(ay+1)%GRID_H
            used.add((ax,ay)); self.p2.static.append(("AA",(ax,ay)))
        self.goto(STATE_DEPLOY)

    def rand_tile(self, ai=False, used=None):
        if used is None: used=set()
        if ai: rx=range(self.board.mid_x+1, GRID_W)
        else:  rx=range(0, self.board.mid_x)
        for _ in range(200):
            gx=random.choice(list(rx)); gy=random.randrange(GRID_H)
            if (gx,gy) not in used: return gx,gy
        return (list(rx)[0], 0)

    def place_facilities(self, side, left=True):
        side.facilities.clear(); used=set()
        xr = range(0, self.board.mid_x-1) if left else range(self.board.mid_x+1, GRID_W)
        for f in ["Power Grid","Nuclear Plant","Stockpile","Weapons Depot","RadarStation"]:
            for _ in range(200):
                gx=random.choice(list(xr)); gy=random.randrange(GRID_H)
                if 0<=gx<GRID_W and 0<=gy<GRID_H and (gx,gy) not in used:
                    used.add((gx,gy)); side.facilities.append((f,(gx,gy))); break

    def draw_status_lines(self):
        if not (self.p1 and self.p2): return
        base_y = HEIGHT - PANEL_H + 12
        p1txt=f"{self.p1.name}  Dmg:{self.p1.damage:.0f}%  Shot:{self.p1.shots_left}  Moves:{self.moves_left}  $:{self.p1.money}  ✦:{self.p1.tokens}"
        p2txt=f"{self.p2.name}  Dmg:{self.p2.damage:.0f}%"
        self.screen.blit(FONT_S.render(p1txt, True, WHITE), (MARGIN_X, base_y))
        self.screen.blit(FONT_S.render(p2txt, True, WHITE), (WIDTH-300, base_y))
        tok=f"Tanks:{self.p1.tank_tokens}  Troops:{self.p1.troop_tokens}  Jets:{self.p1.jet_tokens}  •  AA:{self.p1.aa_tokens}  Radar:{self.p1.radar_tokens}"
        self.screen.blit(FONT_S.render(tok, True, LIGHTGRAY), (MARGIN_X, base_y+20))
        keys="Keys — 1:Tank  2:Troop  3:Jet  5:AA  6:Radar"
        self.screen.blit(FONT_XS.render(keys, True, LIGHTGRAY), (MARGIN_X, base_y+40))

    def draw_country_summary(self, key, pos):
        data=COUNTRIES[key]; x,y=pos; box=pygame.Rect(x,y,480,260)
        pygame.draw.rect(self.screen,(32,35,44),box,border_radius=10); pygame.draw.rect(self.screen,WHITE,box,2,border_radius=10)
        title = FONT.render(f"{key}  •  Build Points: {data['build_points']}", True, WHITE)
        self.screen.blit(title,(x+12,y+12))
        g=data["ground"]; a=data["air"]; n=data["naval"]
        lines=[
            f"Ground: tanks {g['tanks']}, artillery {g['artillery']}, personnel {g['personnel']}",
            f"Air: total {a['aircraft_total']}, fighters {a['fighters']}, bombers {a['bombers']}",
            f"Naval: ships {n['ships']}, carriers {n['carriers']}, subs {n['subs']}",
            f"Defense: air defense rating {data['defense']['air_defense']}",
            "Missiles: " + ", ".join([f"{m['name']}({m['range_km']}km,r={m.get('radius',1)})" for m in data['missiles']]+["AR Missile(700km,r=1)"])
        ]
        for i,ln in enumerate(lines): 
            self.screen.blit(FONT_S.render(ln, True, LIGHTGRAY),(x+12,y+50+i*22))

    def draw_facilities(self, side):
        for f,(gx,gy) in side.facilities:
            gx=max(0,min(GRID_W-1,gx)); gy=max(0,min(GRID_H-1,gy))
            x,y=self.board.pixel_of_grid(gx,gy)
            pygame.draw.rect(self.screen,(120,220,120),(x+6,y+6,TILE-12,TILE-12),2)
            self.screen.blit(FONT_S.render(f.split()[0], True, (120,220,120)), (x+8,y+10))

    def draw_reveal_overlay(self, reveal_tiles):
        for (gx,gy) in reveal_tiles:
            x,y=self.board.pixel_of_grid(gx,gy); s=pygame.Surface((TILE,TILE), pygame.SRCALPHA); s.fill((255,255,255,38)); self.screen.blit(s,(x,y))

    def draw_destroyed_marks(self):
        for (gx,gy) in self.destroyed_tiles:
            x,y=self.board.pixel_of_grid(gx,gy)
            pygame.draw.line(self.screen,(240,90,90),(x+6,y+6),(x+TILE-6,y+TILE-6),3)
            pygame.draw.line(self.screen,(240,90,90),(x+TILE-6,y+6),(x+6,y+TILE-6),3)

    def draw_help_overlay(self, title="How to Play"):
        overlay=pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA); overlay.fill((10,12,16,220)); self.screen.blit(overlay,(0,0))
        lines=self.wrap_text(self.help_text, max_chars=96); w=1000; h=28+6+22*len(lines)+40
        x=(WIDTH-w)//2; y=(HEIGHT-h)//2; panel=pygame.Rect(x,y,w,h)
        pygame.draw.rect(self.screen,(28,30,38),panel,border_radius=12); pygame.draw.rect(self.screen,WHITE,panel,2,border_radius=12)
        self.screen.blit(FONT.render(title, True, WHITE),(x+16,y+16))
        ty=y+44
        for ln in lines: self.screen.blit(FONT_S.render(ln, True, (210,210,220)), (x+16,ty)); ty+=22
        self.screen.blit(FONT_S.render("Click anywhere to go back.", True, (180,180,200)), (x+16,y+h-30))

    def finish_deploy(self): self.goto(STATE_PLAYER)

    def pixel_center(self, gx,gy):
        x,y=self.board.pixel_of_grid(gx,gy); return x+TILE//2, y+TILE//2

    def find_interceptor(self, deff, gx,gy):
        r_rng = RADAR_RANGE_BASE + deff.radar_range_bonus
        a_rng = AA_RANGE_BASE + deff.aa_range_bonus
        has_radar=False
        for t,(rx,ry) in deff.static:
            if t=="Radar" and abs(rx-gx)+abs(ry-gy)<=r_rng: has_radar=True; break
        if not has_radar: return None
        best=None; bd=999
        for t,(ax,ay) in deff.static:
            if t=="AA":
                d=abs(ax-gx)+abs(ay-gy)
                if d<=a_rng and d<bd: bd=d; best=(ax,ay)
        return best

    def resolve_clash(self, atk_type, def_type):
        if atk_type=="Jet" and def_type in ("Tank","Troop"): return "attacker"
        if atk_type=="Tank" and def_type=="Troop": return "attacker"
        if def_type=="Jet" and atk_type in ("Tank","Troop"): return "defender"
        if def_type=="Tank" and atk_type=="Troop": return "defender"
        a=UNIT_META[atk_type]["power"] + random.random()
        d=UNIT_META[def_type]["power"] + random.random()
        return "attacker" if a>=d else "defender"

    def player_click(self, event):
        if event.type==pygame.MOUSEBUTTONDOWN:
            if self.state==STATE_MENU and self.help_open:
                if not self.btn_help.rect.collidepoint(event.pos):
                    self.help_open=False
                return
            if self.market_open and event.button==1:
                self.handle_market_click(event.pos); return

            self.btn_main_menu_br.handle(event)
            if self.state in (STATE_DEPLOY, STATE_PLAYER, STATE_ANIM_MISSILE, STATE_ANIM_MOVES):
                self.btn_market.handle(event)
            if self.state==STATE_DEPLOY:
                self.btn_start_battle.handle(event)

            gp=self.board.grid_at_pixel(event.pos)

            if self.state==STATE_PLAYER and self.selected_missile:
                if gp:
                    gx,gy=gp
                    if self.range_center is None:
                        if gx<self.board.mid_x:
                            self.range_center=(gx,gy)
                            return
                    else:
                        if gx>=self.board.mid_x and self.p1.shots_left>0:
                            r=max(1,int(self.selected_missile.range_km/KM_PER_TILE))
                            if abs(gx-self.range_center[0])+abs(gy-self.range_center[1])<=r:
                                self.p1.shots_left-=1
                                self.launch_missile(self.p1, self.p2, self.range_center, (gx,gy), self.selected_missile, +1)
                                self.selected_missile=None; self.range_center=None
                                return
                return

            if not gp and event.button==1 and self.state==STATE_PLAYER:
                mx=MARGIN_X; by=HEIGHT-44
                for m in self.p1.missiles:
                    rect=pygame.Rect(mx,by,260,26)
                    if rect.collidepoint(event.pos):
                        self.selected_missile=m
                        self.deploy_choice=None
                        self.range_center=None; self.selected_unit_idx=None
                        return
                    mx+=270
                return

            if not gp: return
            gx,gy=gp

            if event.button==3 and gx<self.board.mid_x and self.state==STATE_DEPLOY:
                idx,t=self.p1.mobile_at(gx,gy)
                if idx is not None:
                    if t=='Tank': self.p1.tank_tokens+=1
                    elif t=='Troop': self.p1.troop_tokens+=1
                    elif t=='Jet': self.p1.jet_tokens+=1
                    del self.p1.units[idx]; self.info="Unit retracted."; self.flash_timer=60; return
                sidx,st = self.p1.static_at(gx,gy)
                if sidx is not None:
                    if st=='AA': self.p1.aa_tokens+=1
                    elif st=='Radar': self.p1.radar_tokens+=1
                    del self.p1.static[sidx]; self.info=f"{st} removed."; self.flash_timer=60; return

            if event.button==1 and self.deploy_choice and gx<self.board.mid_x and self.p1.mobile_at(gx,gy)[0] is None and not self.p1.has_static_at(gx,gy):
                if self.state==STATE_DEPLOY or (self.state==STATE_PLAYER and self.moves_left>0):
                    placed=False
                    ch=self.deploy_choice
                    if ch=='Tank' and self.p1.tank_tokens>0: self.p1.units.append(('Tank',(gx,gy),+1)); self.p1.tank_tokens-=1; placed=True
                    elif ch=='Troop' and self.p1.troop_tokens>0: self.p1.units.append(('Troop',(gx,gy),+1)); self.p1.troop_tokens-=1; placed=True
                    elif ch=='Jet' and self.p1.jet_tokens>0: self.p1.units.append(('Jet',(gx,gy),+1)); self.p1.jet_tokens-=1; placed=True
                    elif ch=='AA' and self.p1.aa_tokens>0: self.p1.static.append(("AA",(gx,gy))); self.p1.aa_tokens-=1; placed=True
                    elif ch=='Radar' and self.p1.radar_tokens>0:
                        self.p1.static.append(("Radar",(gx,gy))); self.p1.radar_tokens-=1; self.radar_flash_timer=120; placed=True
                    if placed and self.state==STATE_PLAYER:
                        self.moves_left -= 1
                        self.plan_and_anim_moves(after_label="AI")
                    return

            if event.button==1 and self.state==STATE_PLAYER:
                idx,t = self.p1.mobile_at(gx,gy)
                if idx is not None:
                    self.selected_unit_idx=idx; return

            if event.button==1 and self.selected_unit_idx is not None and self.state==STATE_PLAYER and self.moves_left>0:
                ut, (ux,uy), d = self.p1.units[self.selected_unit_idx]
                rng = UNIT_META[ut]["range"]
                if rng<=0: self.info="This unit cannot move."; self.flash_timer=60; self.selected_unit_idx=None; return
                if abs(gx-ux)+abs(gy-uy)<=rng:
                    path=[]; cx,cy=ux,uy
                    dx = 1 if gx>cx else -1 if gx<cx else 0
                    dy = 1 if gy>cy else -1 if gy<cy else 0
                    while (cx,cy)!=(gx,gy) and len(path)<rng:
                        if cx!=gx: cx+=dx
                        elif cy!=gy: cy+=dy
                        path.append((cx,cy))
                    if path:
                        self.p1.orders.append({"idx":self.selected_unit_idx,"path":path,"type":ut,"dir": +1})
                        self.moves_left -= 1
                        self.plan_and_anim_moves(after_label="AI")
                    self.selected_unit_idx=None

        if event.type==pygame.KEYDOWN:
            if   event.key==pygame.K_ESCAPE and self.market_open: self.market_open=False
            elif event.key==pygame.K_1: self.deploy_choice='Tank'
            elif event.key==pygame.K_2: self.deploy_choice='Troop'
            elif event.key==pygame.K_3: self.deploy_choice='Jet'
            elif event.key==pygame.K_5: self.deploy_choice='AA'
            elif event.key==pygame.K_6: self.deploy_choice='Radar'
            elif event.key==pygame.K_h: self.toggle_help()

    def launch_missile(self, attacker, defender, launch_xy, target_xy, missile, dir=+1):
        sx,sy=self.board.pixel_of_grid(*launch_xy); sx+=TILE//2; sy+=TILE//2
        tx,ty=self.board.pixel_of_grid(*target_xy); tx+=TILE//2; ty+=TILE//2
        dist=math.hypot(tx-sx,ty-sy); steps=max(42,int(dist/6))
        path=[(int(sx+(tx-sx)*i/steps), int(sy+(ty-sy)*i/steps)) for i in range(steps+1)]
        self.anim["missile"]={"att":attacker,"def":defender,"missile":missile,"path":path,"idx":0,"target":target_xy,"dir":dir,"hold":2,"hold_tick":2}
        self.anim["intercept"]=None
        self.goto(STATE_ANIM_MISSILE)

    def missile_grid_at(self, px,py):
        gx=(px - MARGIN_X)//TILE; gy=(py - MARGIN_Y)//TILE
        gx=max(0,min(GRID_W-1,gx)); gy=max(0,min(GRID_H-1,gy)); return gx,gy

    def resolve_missile(self, att, deff, target_xy, missile):
        r=max(1,missile.radius_tiles)
        affected=set()
        for gx in range(target_xy[0]-r, target_xy[0]+r+1):
            for gy in range(target_xy[1]-r, target_xy[1]+r+1):
                if 0<=gx<GRID_W and 0<=gy<GRID_H and abs(gx-target_xy[0])+abs(gy-target_xy[1])<=r:
                    affected.add((gx,gy))
                    px,py=self.board.pixel_of_grid(gx,gy); self.explosions.append(Explosion((px+TILE//2, py+TILE//2),life=32))
                    if att.is_human: self.revealed_p1.add((gx,gy))
                    else: self.revealed_p2.add((gx,gy))
        enemy_units=set(pos for _,pos,_ in deff.units)
        enemy_defs=set(pos for _,pos in deff.static)
        enemy_facs=set(pos for _,pos in deff.facilities)
        asset_hits=0
        deff.units=[u for u in deff.units if u[1] not in affected or False]
        deff.static=[u for u in deff.static if u[1] not in affected or False]
        deff.facilities=[f for f in deff.facilities if f[1] not in affected or False]
        for t in affected:
            if t in enemy_units or t in enemy_defs or t in enemy_facs:
                asset_hits+=1; self.destroyed_tiles.add(t)
        base = int(missile.damage*0.75) if asset_hits>0 else random.randint(0,1)
        bonus = max(0, asset_hits-1) * 4
        total = min(40, base + bonus)
        deff.damage=min(100, deff.damage+total)
        att.money += 5*total + 15*asset_hits; att.tokens += asset_hits
        self.info=f"{att.name} {missile.name} +{total}%  Hits:{asset_hits}  $+{5*total + 15*asset_hits}"
        self.flash_timer=120
        self.check_game_end()

    def plan_and_anim_moves(self, after_label="AI"):
        self.move_snapshot["p1"]=list(self.p1.units)
        self.move_snapshot["p2"]=list(self.p2.units)
        seq=[]
        for order in self.p1.orders:
            idx=order["idx"]
            if idx < 0 or idx >= len(self.p1.units): continue
            t,(gx,gy),d = self.p1.units[idx]
            for step in order["path"]:
                seq.append({"owner":"p1","t":t,"dir":+1,"start":(gx,gy),"end":step,"speed":UNIT_META[t]["speed"],"uid":idx})
                gx,gy=step
            self.p1.units[idx]=(t,(gx,gy),+1)
        self.p1.orders.clear()
        self.anim["moves"]={"seq":seq,"idx":0,"frames": (seq[0]["speed"] if seq else 0)}
        self.anim["after"]=after_label
        self.goto(STATE_ANIM_MOVES)

    def ai_take_turn(self):
        if random.random()<0.5 and self.p2.missiles:
            m=random.choice(self.p2.missiles)
            launch_candidates=[(x, random.randrange(GRID_H)) for x in range(self.board.mid_x+1, GRID_W)]
            random.shuffle(launch_candidates); r=max(1,int(m.range_km/KM_PER_TILE)); best=None; best_score=-1
            for launch in launch_candidates[:60]:
                for gx in range(0,self.board.mid_x):
                    for gy in range(GRID_H):
                        if abs(gx-launch[0])+abs(gy-launch[1])<=r:
                            score=1+(GRID_H//2-abs(gy-GRID_H//2))*0.1
                            if score>best_score: best_score=score; best=(launch,(gx,gy))
            if best:
                self.launch_missile(self.p2,self.p1,best[0],best[1],m,dir=-1)
                return True
        movable=[(i,u) for i,u in enumerate(self.p2.units) if UNIT_META[u[0]]["range"]>0]
        if movable:
            i,u=random.choice(movable)
            t,(gx,gy),d=u
            rng=UNIT_META[t]["range"]; steps=min(rng, max(0, gx - (self.board.mid_x-1)))
            seq=[]
            for s in range(steps):
                nx=max(self.board.mid_x, gx-1); ny=gy
                seq.append({"owner":"p2","t":t,"dir":-1,"start":(gx,gy),"end":(nx,ny),"speed":UNIT_META[t]["speed"],"uid":i})
                gx,gy=nx,ny
            if seq:
                self.move_snapshot["p1"]=list(self.p1.units)
                self.move_snapshot["p2"]=list(self.p2.units)
                self.p2.units[i]=(t,(gx,gy),-1)
                self.anim["moves"]={"seq":seq,"idx":0,"frames": seq[0]["speed"]}
                self.anim["after"]="PLAYER"
                self.goto(STATE_ANIM_MOVES)
                return True
        return False

    def draw_menu(self):
        self.board.draw(self.screen)
        title = FONT_XL.render("WarBoard: Vengeance", True, WHITE)
        tx = biased_center_x(0.08)
        self.screen.blit(title, title.get_rect(midtop=(tx, HEIGHT//2-120)))
        self.btn_start.draw(self.screen); self.btn_help.draw(self.screen)
        if self.help_open: self.draw_help_overlay("How to Play — click anywhere to close")

    def draw_select(self):
        self.board.draw(self.screen)
        if self.dd_p1.selected: self.draw_country_summary(self.dd_p1.selected,(WIDTH//2-520, 220))
        if self.dd_p2.selected: self.draw_country_summary(self.dd_p2.selected,(WIDTH//2+40,  220))
        self.dd_p1.draw(self.screen); self.dd_p2.draw(self.screen); self.btn_confirm.draw(self.screen)
        self.dd_p1.draw_list(self.screen); self.dd_p2.draw_list(self.screen)
        self.btn_main_menu_br.draw(self.screen)

    def draw_deploy(self):
        self.board.draw(self.screen)
        self.btn_market.draw(self.screen)
        self.btn_start_battle.draw(self.screen)
        self.btn_main_menu_br.draw(self.screen)
        self.draw_facilities(self.p1); self.draw_facilities(self.p2)
        draw_static_defenses(self.screen, self.p1, board=self.board)
        draw_units_for_side(self.screen, self.p1, board=self.board)
        if self.radar_flash_timer>0:
            for t,(gx,gy) in self.p1.static:
                if t=="Radar": highlight_range(self.screen,(gx,gy),RADAR_RANGE_BASE+self.p1.radar_range_bonus,self.board,(120,220,120))
        self.draw_status_lines()
        if self.market_open: self.draw_market_overlay()

    def draw_player(self):
        self.board.draw(self.screen)
        self.btn_market.draw(self.screen)
        self.btn_main_menu_br.draw(self.screen)
        self.draw_facilities(self.p1); self.draw_facilities(self.p2)
        reveal_tiles = set(self.radar_cover_p1) | set(self.revealed_p1)
        draw_static_defenses(self.screen, self.p1, board=self.board)
        draw_static_defenses(self.screen, self.p2, reveal_set=reveal_tiles, is_enemy=True, board=self.board)
        draw_units_for_side(self.screen, self.p1, board=self.board)
        draw_units_for_side(self.screen, self.p2, reveal_set=reveal_tiles, is_enemy=True, board=self.board)
        self.draw_reveal_overlay(reveal_tiles)
        self.draw_destroyed_marks()
        mx=MARGIN_X; by=HEIGHT-44
        self.screen.blit(FONT_S.render("Missiles:", True, WHITE), (mx, HEIGHT-70))
        for m in self.p1.missiles:
            rect=pygame.Rect(mx,by,260,26); sel=(self.selected_missile is m)
            pygame.draw.rect(self.screen,(70,70,70),rect,border_radius=6); pygame.draw.rect(self.screen,(255,255,255) if sel else (140,140,140),rect,2,border_radius=6)
            self.screen.blit(FONT_XS.render(f"{m.name} ({m.range_km}km, r={m.radius_tiles})", True, WHITE),(rect.x+6,rect.y+5)); mx+=270
        if self.selected_unit_idx is not None:
            t,(ux,uy),d = self.p1.units[self.selected_unit_idx]
            highlight_range(self.screen,(ux,uy),UNIT_META[t]["range"], self.board)
        if self.selected_missile and self.range_center:
            cx,cy=self.range_center; rt=max(1,int(self.selected_missile.range_km/KM_PER_TILE))
            for gx in range(self.board.mid_x, GRID_W):
                for gy in range(GRID_H):
                    if abs(gx-cx)+abs(gy-cy)<=rt:
                        x,y=self.board.pixel_of_grid(gx,gy); pygame.draw.rect(self.screen,(100,100,100),(x+3,y+3,TILE-6,TILE-6),1)
        if self.radar_flash_timer>0:
            for t,(gx,gy) in self.p1.static:
                if t=="Radar": highlight_range(self.screen,(gx,gy),RADAR_RANGE_BASE+self.p1.radar_range_bonus,self.board,(120,220,120))
        self.draw_status_lines()
        if self.market_open: self.draw_market_overlay()

    def draw_anim_missile(self):
        self.board.draw(self.screen)
        self.btn_main_menu_br.draw(self.screen)
        self.draw_facilities(self.p1); self.draw_facilities(self.p2)
        reveal_tiles = set(self.radar_cover_p1) | set(self.revealed_p1)
        draw_static_defenses(self.screen, self.p1, board=self.board)
        draw_static_defenses(self.screen, self.p2, reveal_set=reveal_tiles, is_enemy=True, board=self.board)
        draw_units_for_side(self.screen, self.p1, board=self.board)
        draw_units_for_side(self.screen, self.p2, reveal_set=reveal_tiles, is_enemy=True, board=self.board)
        m=self.anim["missile"]
        if m: px,py=m["path"][m["idx"]]; draw_missile_sprite(self.screen, px,py, m["dir"])
        if self.anim["intercept"]:
            ip=self.anim["intercept"]; ipx,ipy=ip["path"][ip["idx"]]
            draw_missile_sprite(self.screen, ipx,ipy, ip["dir"])
        self.draw_reveal_overlay(reveal_tiles); self.draw_destroyed_marks()
        self.draw_status_lines()
        if self.market_open: self.draw_market_overlay()

    def draw_anim_moves(self):
        self.board.draw(self.screen)
        self.btn_main_menu_br.draw(self.screen)
        for t,(gx,gy),d in (self.move_snapshot["p1"] or []): draw_unit_icon(self.screen, t, gx,gy, d, enemy=False)
        for t,(gx,gy),d in (self.move_snapshot["p2"] or []):
            if (gx,gy) in self.radar_cover_p1 or (gx,gy) in self.revealed_p1: draw_unit_icon(self.screen, t, gx,gy, d, enemy=True)
        draw_static_defenses(self.screen, self.p1, board=self.board)
        draw_static_defenses(self.screen, self.p2, reveal_set=(self.radar_cover_p1|self.revealed_p1), is_enemy=True, board=self.board)
        mv=self.anim["moves"]
        if mv and mv["idx"]<len(mv["seq"]):
            step=mv["seq"][mv["idx"]]; t=1.0 - mv["frames"]/step["speed"]
            sx,sy=step["start"]; ex,ey=step["end"]
            ix=int(sx + (ex-sx)*t); iy=int(sy + (ey-sy)*t)
            draw_unit_icon(self.screen, step["t"], ix,iy, step["dir"], enemy=(step["owner"]=="p2"))
        self.draw_destroyed_marks()
        self.draw_status_lines()
        if self.market_open: self.draw_market_overlay()

    def handle_market_click(self, pos):
        if not self.p1: return
        if self.market_close_rect.collidepoint(pos): self.market_open=False; return
        if not self.market_rect.collidepoint(pos): self.market_open=False; return
        for r,item in getattr(self,'market_clickzones',[]):
            if r.collidepoint(pos):
                if self.p1.money >= item["price"]:
                    self.p1.money -= item["price"]
                    if "missile" in item:
                        n,rg,dm,rd=item["missile"]
                        anti=item.get("anti",False)
                        self.p1.missiles.append(Missile(n,rg,dm,rd,anti_radar=anti)); self.info=f"Bought {n}"
                    elif item.get("grant")=="AA":
                        self.p1.aa_tokens+=1; self.info=f"Bought {item['name']} (AA token +1)"
                        perk=item.get("perk")
                        if perk=="s400": self.p1.aa_range_bonus += 1
                        elif perk=="patriot": self.p1.intercept_cash_bonus += 10
                        elif perk=="akash": self.p1.intercept_cash_bonus += 5
                        elif perk=="irondome": self.p1.intercept_cash_bonus += 8
                    elif item.get("grant")=="Radar":
                        self.p1.radar_tokens+=1; self.p1.radar_range_bonus += 1; self.radar_flash_timer=120; self.info=f"Bought {item['name']} (Radar token +1, +range)"
                    else:
                        if item["name"]=="Tank": self.p1.tank_tokens+=1
                        elif item["name"]=="Troop": self.p1.troop_tokens+=1
                        elif item["name"]=="Jet": self.p1.jet_tokens+=1
                        self.info=f"Bought {item['name']}. Place with 1–3/5–6."
                else:
                    self.info="Not enough money"
                self.flash_timer=90
                break

    def draw_market_overlay(self):
        overlay=pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA); overlay.fill((10,12,16,230)); self.screen.blit(overlay,(0,0))
        w=960; h=520; x=(WIDTH-w)//2; y=(HEIGHT-h)//2
        self.market_rect=pygame.Rect(x,y,w,h)
        pygame.draw.rect(self.screen,(28,30,38),self.market_rect,border_radius=14); pygame.draw.rect(self.screen,WHITE,self.market_rect,2,border_radius=14)
        self.screen.blit(FONT.render("Market — click to buy (place with 1–3/5–6)", True, WHITE),(x+16,y+16))
        self.screen.blit(FONT_S.render("ESC / Close / outside click to close", True, LIGHTGRAY),(x+16,y+44))
        close_rect=pygame.Rect(x+w-44,y+12,32,28)
        pygame.draw.rect(self.screen,(80,80,90),close_rect,border_radius=6); pygame.draw.rect(self.screen,WHITE,close_rect,1,border_radius=6)
        self.screen.blit(FONT_S.render("Close", True, WHITE),(close_rect.x-18, close_rect.y+30))
        self.market_close_rect=close_rect
        if self.p1:
            self.screen.blit(FONT_S.render(f"Money: {self.p1.money}   Tokens: {self.p1.tokens}", True, LIGHTGRAY),(x+w-280,y+18))
        cols=3; item_w=(w-40)//cols; item_h=96; self.market_clickzones=[]
        for i,item in enumerate(self.market_items):
            cx=x+16+(i%cols)*item_w; cy=y+74+(i//cols)*(item_h+14)
            r=pygame.Rect(cx,cy,item_w-20,item_h)
            pygame.draw.rect(self.screen,(40,44,54),r,border_radius=10); pygame.draw.rect(self.screen,(200,200,210),r,1,border_radius=10)
            self.screen.blit(FONT.render(item["name"], True, WHITE),(r.x+10,r.y+10))
            self.screen.blit(FONT_S.render(f"${item['price']}", True, (200,220,200)),(r.x+10,r.y+42))
            self.screen.blit(FONT_XS.render("Adds missile or unit tokens to inventory", True, (180,185,195)),(r.x+10,r.y+64))
            self.market_clickzones.append((r,item))

    def check_game_end(self):
        if not (self.p1 and self.p2): return
        if self.p1.damage>=100 or self.p2.damage>=100:
            self.goto(STATE_GAME_OVER)

    def update(self):
        if self.flash_timer>0: self.flash_timer-=1
        if self.radar_flash_timer>0: self.radar_flash_timer-=1
        if self.state==STATE_GAME_OVER and self.game_over_timer>0:
            self.game_over_timer -= 1
            if self.game_over_timer==0:
                self.reset_to_menu()

        self.radar_cover_p1=set(); self.radar_cover_p2=set()
        if self.p1:
            for t,(gx,gy) in self.p1.static:
                if t=="Radar":
                    r_rng = RADAR_RANGE_BASE + self.p1.radar_range_bonus
                    for x in range(max(self.board.mid_x, gx-r_rng), min(GRID_W, gx+r_rng+1)):
                        for y in range(max(0, gy-r_rng), min(GRID_H, gy+r_rng+1)):
                            if abs(x-gx)+abs(y-gy)<=r_rng: self.radar_cover_p1.add((x,y))
        if self.p2:
            for t,(gx,gy) in self.p2.static:
                if t=="Radar":
                    r_rng = RADAR_RANGE_BASE + self.p2.radar_range_bonus
                    for x in range(max(0, gx-r_rng), min(self.board.mid_x, gx+r_rng+1)):
                        for y in range(max(0, gy-r_rng), min(GRID_H, gy+r_rng+1)):
                            if abs(x-gx)+abs(y-gy)<=r_rng: self.radar_cover_p2.add((x,y))

        if self.p1 and self.p2:
            for t,(rx,ry) in self.p1.static:
                if t=="Radar":
                    for ut,(gx,gy),d in self.p2.units:
                        if abs(gx-rx)+abs(gy-ry)<=RADAR_RANGE_BASE+self.p1.radar_range_bonus:
                            self.revealed_p2.add((rx,ry)); break
            for t,(rx,ry) in self.p2.static:
                if t=="Radar":
                    for ut,(gx,gy),d in self.p1.units:
                        if abs(gx-rx)+abs(gy-ry)<=RADAR_RANGE_BASE+self.p2.radar_range_bonus:
                            self.revealed_p1.add((rx,ry)); break

        if self.state==STATE_ANIM_MISSILE:
            if self.anim["intercept"]:
                ip=self.anim["intercept"]; ip["idx"]+=1
                if ip["idx"]>=len(ip["path"]):
                    self.explosions.append(Explosion((ip["path"][-1][0], ip["path"][-1][1]),life=18))
                    deff=self.anim["missile"]["def"]
                    deff.money += 35 + deff.intercept_cash_bonus
                    self.info="AA intercepted."; self.flash_timer=90
                    att = "ai" if (not self.anim["missile"]["att"].is_human) else "human"
                    self.anim["missile"]=None; self.anim["intercept"]=None
                    if att=="ai": self.goto(STATE_PLAYER)
                    else: self.plan_and_anim_moves(after_label="AI")
                    return

            m=self.anim["missile"]
            if not m: return
            m["hold_tick"]-=1
            if m["hold_tick"]<=0:
                m["idx"]+=1; m["hold_tick"]=m["hold"]
                if m["idx"]<len(m["path"]):
                    px,py=m["path"][m["idx"]]; gx,gy=self.missile_grid_at(px,py)
                    if self.anim["intercept"] is None:
                        if not m["missile"].anti_radar:
                            aa_pos=self.find_interceptor(m["def"], gx,gy)
                        else:
                            aa_pos=None
                        if aa_pos:
                            ax,ay=self.board.pixel_of_grid(*aa_pos); ax+=TILE//2; ay+=TILE//2
                            steps= max(12, int(math.hypot(px-ax,py-ay)/10))
                            ipath=[(int(ax+(px-ax)*i/steps), int(ay+(py-ay)*i/steps)) for i in range(steps+1)]
                            idir= +1 if m["dir"]<0 else -1
                            self.anim["intercept"]={"path":ipath,"idx":0,"dir":idir}
                if m and m["idx"]>=len(m["path"]):
                    self.resolve_missile(m["att"], m["def"], m["target"], m["missile"])
                    if self.state!=STATE_GAME_OVER:
                        if m["att"].is_human: self.plan_and_anim_moves(after_label="AI")
                        else: self.goto(STATE_PLAYER)
                    self.anim["missile"]=None

        elif self.state==STATE_ANIM_MOVES:
            mv=self.anim["moves"]
            if mv and mv["idx"]<len(mv["seq"]):
                mv["frames"]-=1
                if mv["frames"]<=0:
                    step=mv["seq"][mv["idx"]]
                    gx,gy=step["end"]
                    if step["t"]=="Jet":
                        if step["owner"]=="p1":
                            aa=self.find_interceptor(self.p2, gx,gy)
                            if aa: 
                                px,py=self.board.pixel_of_grid(gx,gy); self.explosions.append(Explosion((px+TILE//2, py+TILE//2),life=22))
                                uid=step.get("uid")
                                if uid is not None and 0<=uid<len(self.p1.units) and self.p1.units[uid][0]=='Jet':
                                    self.p1.units.pop(uid)
                                else:
                                    self.p1.units=[u for u in self.p1.units if not (u[0]=='Jet' and u[2]==+1)]
                                self.p2.money += 25 + self.p2.intercept_cash_bonus; self.info="Enemy AA shot down your jet."; self.flash_timer=90
                                mv["idx"]=len(mv["seq"])
                        else:
                            aa=self.find_interceptor(self.p1, gx,gy)
                            if aa:
                                px,py=self.board.pixel_of_grid(gx,gy); self.explosions.append(Explosion((px+TILE//2, py+TILE//2),life=22))
                                uid=step.get("uid")
                                if uid is not None and 0<=uid<len(self.p2.units) and self.p2.units[uid][0]=='Jet':
                                    self.p2.units.pop(uid)
                                else:
                                    self.p2.units=[u for u in self.p2.units if not (u[0]=='Jet' and u[2]==-1)]
                                self.p1.money += 25 + self.p1.intercept_cash_bonus; self.info="AA shot down enemy jet."; self.flash_timer=90
                                mv["idx"]=len(mv["seq"])
                    if mv["idx"]<len(mv["seq"]):
                        if step["owner"]=="p1":
                            for j,(t,(ux,uy),d) in enumerate(list(self.p2.units)):
                                if (ux,uy)==(gx,gy):
                                    outcome=self.resolve_clash(step["t"], t)
                                    px,py=self.board.pixel_of_grid(gx,gy); self.explosions.append(Explosion((px+TILE//2, py+TILE//2),life=22))
                                    if outcome=="attacker":
                                        del self.p2.units[j]; self.revealed_p1.add((gx,gy))
                                    else:
                                        if step.get("uid") is not None and 0<=step["uid"]<len(self.p1.units):
                                            self.p1.units.pop(step["uid"])
                                        else:
                                            self.p1.units=[u for u in self.p1.units if not (u[0]==step["t"] and u[2]==+1)]
                                    break
                        else:
                            for j,(t,(ux,uy),d) in enumerate(list(self.p1.units)):
                                if (ux,uy)==(gx,gy):
                                    outcome=self.resolve_clash(step["t"], t)
                                    px,py=self.board.pixel_of_grid(gx,gy); self.explosions.append(Explosion((px+TILE//2, py+TILE//2),life=22))
                                    if outcome=="attacker":
                                        del self.p1.units[j]
                                    else:
                                        if step.get("uid") is not None and 0<=step["uid"]<len(self.p2.units):
                                            self.p2.units.pop(step["uid"])
                                        else:
                                            self.p2.units=[u for u in self.p2.units if not (u[0]==step["t"] and u[2]==-1)]
                                    break
                        mv["idx"]+=1
                        if mv["idx"]<len(mv["seq"]): mv["frames"]=mv["seq"][mv["idx"]]["speed"]
            else:
                if self.p1:
                    occ_gain=sum(UNIT_META[t]["power"] for t,(gx,gy),d in self.p1.units if gx>=self.board.mid_x)
                    self.p2.damage=min(100, self.p2.damage+occ_gain)
                    self.check_game_end()
                if self.state!=STATE_GAME_OVER:
                    if not self.ai_take_turn(): self.goto(STATE_PLAYER)

    def handle_menu(self, event):
        self.btn_start.handle(event); self.btn_help.handle(event)
        if self.help_open and event.type==pygame.MOUSEBUTTONDOWN and not self.btn_help.rect.collidepoint(event.pos):
            self.help_open=False

    def handle_select(self, event):
        self.dd_p1.handle(event); self.dd_p2.handle(event); self.btn_confirm.handle(event); self.btn_main_menu_br.handle(event)

    def run(self):
        running=True
        while running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type==pygame.QUIT: running=False
                elif self.state in (STATE_DEPLOY, STATE_PLAYER, STATE_ANIM_MISSILE, STATE_ANIM_MOVES):
                    self.player_click(event)
                elif self.state==STATE_MENU: self.handle_menu(event)
                elif self.state==STATE_SELECT: self.handle_select(event)
                elif self.state==STATE_GAME_OVER and (event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN)):
                    self.reset_to_menu()

            if self.state==STATE_MENU: self.draw_menu()
            elif self.state==STATE_SELECT: self.draw_select()
            elif self.state==STATE_DEPLOY: self.draw_deploy()
            elif self.state==STATE_PLAYER: self.draw_player()
            elif self.state==STATE_ANIM_MISSILE: self.draw_anim_missile()
            elif self.state==STATE_ANIM_MOVES: self.draw_anim_moves()
            elif self.state==STATE_GAME_OVER:
                self.board.draw(self.screen)
                winner = self.p1.name if self.p2.damage>=100 else self.p2.name if self.p1.damage>=100 else "None"
                msg = f"Game Over • Winner: {winner}  (click to return)"
                self.screen.blit(FONT_L.render(msg, True, YELLOW), (WIDTH//2-360, HEIGHT//2-20))
                self.btn_main_menu_br.draw(self.screen)

            for ex in list(self.explosions):
                ex.draw(self.screen)
                if ex.life<=0: self.explosions.remove(ex)

            self.update(); pygame.display.flip()

if __name__=="__main__":
    Game().run()
