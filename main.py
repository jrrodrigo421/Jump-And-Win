import os
import sys
import random
import math
import json
import pygame
from pygame import mixer

# psycopg2 para conectar ao PostgreSQL (Neon)
import psycopg2
import psycopg2.extras

pygame.init()
mixer.init()

# ----------------------------------------------------------------------
# 1) CONFIGURAÇÃO DE ACESSO AO BANCO (NEON)
# ----------------------------------------------------------------------
# DATABASE_URL = os.getenv("DATABASE_URL") # Ex: "postgres://user:pass@host:port/dbname"
DATABASE_URL="postgresql://neondb_owner:npg_Iq4Sa0wsodNn@ep-patient-bonus-a8xsj6el-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
print('DATABASE_URL: >>>>>>>>>', DATABASE_URL)

def db_connect():
    """Retorna uma conexão para o banco de dados Neon."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def db_init():
    """Cria as tabelas se não existirem."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    balance INT,
                    daily_score INT,
                    high_score INT,
                    shield INT,
                    double_jump INT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    score INT,
                    date TIMESTAMP DEFAULT now()
                );
            """)
            conn.commit()

def db_get_user(username):
    """Retorna um dicionário com os dados do usuário ou None se não existir."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)  # row é RealDictRow, então dict(row) vira um dicionário

def db_create_user(username, initial_balance=100):
    """Cria novo usuário no banco, com contadores de shield e double_jump = 0."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (username, balance, daily_score, high_score, shield, double_jump)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                username,
                initial_balance,
                0,
                0,
                0,
                0
            ))
            conn.commit()

def db_update_user(user):
    """Atualiza os dados do usuário no banco."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET balance = %s,
                    daily_score = %s,
                    high_score = %s,
                    shield = %s,
                    double_jump = %s
                WHERE username = %s
            """, (
                user["balance"],
                user["daily_score"],
                user["high_score"],
                user["shield"],
                user["double_jump"],
                user["username"]
            ))
            conn.commit()

def db_save_score(username, score):
    """Salva um score na tabela scores."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO scores (username, score)
                VALUES (%s, %s)
            """, (username, score))
            conn.commit()

def db_get_top_scores(limit=10):
    """Retorna os top N scores."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, score
                FROM scores
                ORDER BY score DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({"name": r["username"], "score": r["score"]})
            return results

# Inicializa as tabelas no banco
db_init()

# ----------------------------------------------------------------------
# 2) CONFIGURAÇÕES DO JOGO
# ----------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("JumpAndWin: 💸")

clock = pygame.time.Clock()
FPS = 60

TITLE_FONT = pygame.font.SysFont("Arial", 48, bold=True)
FONT = pygame.font.SysFont("Arial", 24)
SMALL_FONT = pygame.font.SysFont("Arial", 18)

WHITE   = (255, 255, 255)
BLACK   = (0, 0, 0)
RED     = (220, 20, 60)
BLUE    = (65, 105, 225)
GREEN   = (34, 139, 34)
YELLOW  = (255, 215, 0)
PURPLE  = (138, 43, 226)
ORANGE  = (255, 140, 0)

GRAVITY = 0.6
BASE_JUMP_POWER = -12
BASE_OBSTACLE_SPEED = 5
PLAY_COST = 10
DOUBLE_JUMP_COST = 5
SHIELD_COST = 15

# Sons
try:
    jump_sound = mixer.Sound('assets/jump.mp3')
    collision_sound = mixer.Sound('assets/game-over.mp3')
    point_sound = mixer.Sound('assets/jump.mp3')
    powerup_sound = mixer.Sound('assets/jump.mp3')
except:
    jump_sound = mixer.Sound(buffer=bytearray(100))
    collision_sound = mixer.Sound(buffer=bytearray(100))
    point_sound = mixer.Sound(buffer=bytearray(100))
    powerup_sound = mixer.Sound(buffer=bytearray(100))

try:
    mixer.music.load('assets/jump.mp3')
except:
    pass

# Variáveis de "pot" diário e dono do jogo
daily_pot = 0
daily_winner = None  # (username, score)
owner_balance = 0

# ----------------------------------------------------------------------
# 3) CLASSES E FUNÇÕES AUXILIARES
# ----------------------------------------------------------------------

class Particle:
    def __init__(self, x, y, color, vel_x=None, vel_y=None, size=None, gravity=None):
        self.x = x
        self.y = y
        self.color = color
        self.vel_x = random.uniform(-3, 3) if vel_x is None else vel_x
        self.vel_y = random.uniform(-6, -1) if vel_y is None else vel_y
        self.size = random.randint(2, 8) if size is None else size
        self.gravity = 0.2 if gravity is None else gravity
        self.life = random.randint(20, 60)

    def update(self):
        self.vel_y += self.gravity
        self.x += self.vel_x
        self.y += self.vel_y
        self.life -= 1

    def draw(self, surface):
        alpha = min(255, self.life * 4)
        s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, alpha), (self.size//2, self.size//2), self.size//2)
        surface.blit(s, (int(self.x), int(self.y)))


class Button:
    def __init__(self, x, y, width, height, text, color=(100,100,100), hover_color=(150,150,150), text_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.active_color = color

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        if self.rect.collidepoint(mouse_pos):
            self.active_color = self.hover_color
        else:
            self.active_color = self.color
        pygame.draw.rect(surface, self.active_color, self.rect, border_radius=10)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=10)
        text_surf = FONT.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False


def draw_cloud(surface, x, y):
    pygame.draw.ellipse(surface, WHITE, (x, y, 60, 30))
    pygame.draw.ellipse(surface, WHITE, (x + 20, y - 10, 40, 30))
    pygame.draw.ellipse(surface, WHITE, (x + 10, y + 5, 50, 25))

def draw_tree(surface, x, y):
    pygame.draw.rect(surface, (139,69,19), (x-5, y-50, 10, 50))
    pygame.draw.circle(surface, (34,139,34), (x, y-60), 25)
    pygame.draw.circle(surface, (34,139,34), (x-15, y-40), 20)
    pygame.draw.circle(surface, (34,139,34), (x+15, y-40), 20)

def draw_cactus(surface, x, y):
    pygame.draw.rect(surface, (50,205,50), (x-5, y-60, 10, 60))
    pygame.draw.rect(surface, (50,205,50), (x-5, y-45, -15, 8))
    pygame.draw.rect(surface, (50,205,50), (x+5, y-30, 15, 8))


def draw_background(surface, score):
    phase = ((score // 10) % 10) + 1
    phase_colors = [
        [(173,216,230), WHITE],
        [(144,238,144), (220,255,220)],
        [(255,165,0), (255,215,0)],
        [(139,0,0), (80,0,0)],
        [(135,206,250), (240,248,255)],
        [(152,251,152), (240,255,240)],
        [(255,192,203), (255,228,225)],
        [(221,160,221), (238,130,238)],
        [(255,218,185), (255,228,196)],
        [(192,192,192), (255,250,250)]
    ]
    top_color, bottom_color = phase_colors[phase - 1]
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(top_color[0]*(1 - ratio) + bottom_color[0]*ratio)
        g = int(top_color[1]*(1 - ratio) + bottom_color[1]*ratio)
        b = int(top_color[2]*(1 - ratio) + bottom_color[2]*ratio)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))

    if phase % 4 == 1:
        for _ in range(5):
            cloud_x = (pygame.time.get_ticks()//50 + random.randint(0,WIDTH)) % (WIDTH+200) - 100
            cloud_y = random.randint(50,150)
            draw_cloud(surface, cloud_x, cloud_y)
    elif phase % 4 == 2:
        for i in range(10):
            tree_x = (i*80 + (pygame.time.get_ticks()//80)%80) % WIDTH
            tree_y = HEIGHT - 100
            draw_tree(surface, tree_x, tree_y)
    elif phase % 4 == 3:
        for i in range(5):
            cactus_x = (i*150 + (pygame.time.get_ticks()//60)%150) % WIDTH
            cactus_y = HEIGHT - 100
            draw_cactus(surface, cactus_x, cactus_y)
    elif phase % 4 == 0:
        lava_height = 50
        lava_y = HEIGHT - lava_height
        for x in range(0, WIDTH, 4):
            wave = math.sin((x + pygame.time.get_ticks()/200)*0.05)*10
            pygame.draw.rect(surface, (255,69,0), (x, lava_y+wave, 4, lava_height-wave))

    ground_color = (100,70,40) if phase < 4 else (50,0,0)
    pygame.draw.rect(surface, ground_color, (0, HEIGHT-50, WIDTH, 50))


# ----------------------------------------------------------------------
# 4) LÓGICA DE LOGIN, MENU, ETC. USANDO BD
# ----------------------------------------------------------------------

def show_message(message, sub_message=""):
    waiting = True
    while waiting:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                waiting = False

        screen.fill((30,30,60))
        lines = message.split('\n')
        for i, line in enumerate(lines):
            text = FONT.render(line, True, WHITE)
            screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - 40 + i*30))

        if sub_message:
            subtext = SMALL_FONT.render(sub_message, True, WHITE)
            screen.blit(subtext, (WIDTH//2 - subtext.get_width()//2, HEIGHT//2 + 40))

        pygame.display.flip()


def login_screen():
    username = ""
    buttons = [
        Button(WIDTH//2 - 100, HEIGHT//2 + 60, 200, 40, "Login", BLUE),
        Button(WIDTH//2 - 100, HEIGHT//2 + 110, 200, 40, "Novo Usuário", GREEN)
    ]
    login_active = True
    error_message = ""
    initial_balance = 100
    login_mode = True

    while login_active:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if login_mode:
                        # Tenta buscar no BD
                        user = db_get_user(username)
                        if user:
                            login_active = False
                        else:
                            error_message = "Usuário não encontrado!"
                    else:
                        # Criar user no BD
                        user = db_get_user(username)
                        if user:
                            error_message = "Usuário já existe!"
                        else:
                            db_create_user(username, initial_balance)
                            login_active = False
                elif event.key == pygame.K_BACKSPACE:
                    username = username[:-1]
                else:
                    if len(username) < 12:
                        username += event.unicode

            for button in buttons:
                if button.is_clicked(event):
                    if button.text == "Login":
                        login_mode = True
                    elif button.text == "Novo Usuário":
                        login_mode = False

        screen.fill((30,30,60))
        title = TITLE_FONT.render("JumpAndWin: 💸", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        prompt_text = FONT.render(
            "Entre com seu nome para logar:" if login_mode else "Crie seu nome para cadastrar:",
            True, WHITE
        )
        screen.blit(prompt_text, (WIDTH//2 - prompt_text.get_width()//2, HEIGHT//2 - 50))

        pygame.draw.rect(screen, WHITE, (WIDTH//2 - 150, HEIGHT//2 - 20, 300, 40), border_radius=5)
        user_text = FONT.render(username, True, BLACK)
        screen.blit(user_text, (WIDTH//2 - 140, HEIGHT//2 - 10))

        if error_message:
            error = FONT.render(error_message, True, RED)
            screen.blit(error, (WIDTH//2 - error.get_width()//2, HEIGHT//2 + 30))

        for button in buttons:
            button.draw(screen)

        pygame.display.flip()

    return username


def main_menu(username):
    buttons = [
        Button(WIDTH//2 - 120, 200, 240, 50, "Jogar", BLUE),
        Button(WIDTH//2 - 120, 270, 240, 50, "Loja", GREEN),
        Button(WIDTH//2 - 120, 340, 240, 50, "Ranking", PURPLE),
        Button(WIDTH//2 - 120, 410, 240, 50, "Como Jogar", YELLOW),
        Button(WIDTH//2 - 120, 480, 240, 50, "Sair", RED)
    ]
    particles = []
    menu_active = True
    selection = None

    # Toca música de menu
    try:
        mixer.music.load('')
        mixer.music.play(-1)
    except:
        pass

    while menu_active:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            for button in buttons:
                if button.is_clicked(event):
                    selection = button.text.lower()
                    menu_active = False

        # Partículas
        if random.random() < 0.1:
            particles.append(Particle(
                random.randint(0, WIDTH),
                random.randint(0, HEIGHT),
                (random.randint(100,255), random.randint(100,255), random.randint(100,255)),
                gravity=0
            ))
        for p in particles[:]:
            p.update()
            if p.life <= 0:
                particles.remove(p)

        screen.fill((30,30,60))
        for p in particles:
            p.draw(screen)

        title = TITLE_FONT.render("JumpAndWin: 💸", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        # Carrega do BD o user
        user = db_get_user(username)
        if user:
            user_info = FONT.render(f"Jogador: {user['username']}    Saldo: {user['balance']}", True, WHITE)
            screen.blit(user_info, (20, 20))
        else:
            user_info = FONT.render(f"Jogador: {username} (não encontrado no BD)", True, RED)
            screen.blit(user_info, (20, 20))

        pot_text = FONT.render(f"Prêmio do Dia: {daily_pot}", True, YELLOW)
        screen.blit(pot_text, (WIDTH - pot_text.get_width() - 20, 20))

        for button in buttons:
            button.draw(screen)

        pygame.display.flip()

    mixer.music.stop()
    return selection


def shop_screen(username):
    shop_items = [
        {"name": "Pulo Duplo", "key": "double_jump", "price": DOUBLE_JUMP_COST, "desc": "Permite um pulo extra", "color": BLUE},
        {"name": "Escudo", "key": "shield", "price": SHIELD_COST, "desc": "Protege contra impacto", "color": GREEN},
    ]
    buttons = [Button(WIDTH//2 - 100, HEIGHT - 80, 200, 40, "Voltar ao Menu", RED)]
    for i, item in enumerate(shop_items):
        buttons.append(Button(WIDTH//2 + 120, 200 + i*100, 150, 40, f"Comprar ({item['price']})", item["color"]))

    shop_active = True

    while shop_active:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            for i, button in enumerate(buttons):
                if button.is_clicked(event):
                    if i == 0:
                        shop_active = False
                    else:
                        # i-1 => item no shop_items
                        item = shop_items[i-1]
                        user = db_get_user(username)
                        if user and user["balance"] >= item["price"]:
                            user["balance"] -= item["price"]
                            user[item["key"]] += 1  # ex: user["shield"] += 1
                            db_update_user(user)
                            powerup_sound.play()

        screen.fill((30,30,60))
        title = TITLE_FONT.render("Loja", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        user = db_get_user(username)
        if user:
            balance_text = FONT.render(f"Seu Saldo: {user['balance']}", True, WHITE)
            screen.blit(balance_text, (WIDTH//2 - balance_text.get_width()//2, 140))

        for i, item in enumerate(shop_items):
            pygame.draw.rect(screen, (60,60,90), (100, 200 + i*100, WIDTH - 200, 80), border_radius=10)
            item_name = FONT.render(item['name'], True, WHITE)
            item_desc = SMALL_FONT.render(item['desc'], True, WHITE)

            # ex: user["double_jump"] ou user["shield"]
            qty = 0
            if user:
                qty = user[item["key"]]

            qty_text = FONT.render(f"Você tem: {qty}", True, item["color"])
            screen.blit(item_name, (120, 210 + i*100))
            screen.blit(item_desc, (120, 240 + i*100))
            screen.blit(qty_text, (350, 210 + i*100))

        for button in buttons:
            button.draw(screen)

        pygame.display.flip()

    return


def ranking_screen():
    buttons = [Button(WIDTH//2 - 100, HEIGHT - 80, 200, 40, "Voltar ao Menu", RED)]
    ranking_active = True

    # Agora pegamos do BD:
    top_scores = db_get_top_scores(10)

    while ranking_active:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            for button in buttons:
                if button.is_clicked(event):
                    ranking_active = False

        screen.fill((30,30,60))
        title = TITLE_FONT.render("Ranking Global", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        if top_scores:
            header = FONT.render("Pos   Jogador                  Pontuação", True, WHITE)
            screen.blit(header, (WIDTH//2 - 200, 150))
            pygame.draw.line(screen, WHITE, (WIDTH//2 - 200, 180), (WIDTH//2 + 200, 180))
            for i, score_data in enumerate(top_scores):
                pos_text = FONT.render(f"{i+1}.", True, YELLOW if i < 3 else WHITE)
                name = score_data["name"][:20]
                name_text = FONT.render(name, True, YELLOW if i < 3 else WHITE)
                sc_text = FONT.render(str(score_data["score"]), True, YELLOW if i < 3 else WHITE)
                screen.blit(pos_text, (WIDTH//2 - 200, 200 + i*30))
                screen.blit(name_text, (WIDTH//2 - 160, 200 + i*30))
                screen.blit(sc_text, (WIDTH//2 + 150, 200 + i*30))
        else:
            no_scores = FONT.render("Ainda não há pontuações registradas", True, WHITE)
            screen.blit(no_scores, (WIDTH//2 - no_scores.get_width()//2, 250))

        for button in buttons:
            button.draw(screen)

        pygame.display.flip()

    return


def tutorial_screen():
    buttons = [Button(WIDTH//2 - 100, HEIGHT - 80, 200, 40, "Voltar ao Menu", RED)]
    tutorial_active = True
    tutorial_pages = [
        {
            "title": "Como Jogar",
            "text": [
                "Controla seu personagem e evite obstáculos.",
                "Colete pontos quanto mais longe chegar.",
                "Use power-ups para melhorar sua performance."
            ]
        },
        {
            "title": "Controles",
            "text": [
                "ESPAÇO - Pular",
                "Z - Pulo Duplo (se disponível)",
                "X - Ativar Escudo (se disponível)",
                "D - Finalizar o dia"
            ]
        },
        {
            "title": "Fases e Dificuldade",
            "text": [
                "10 fases diferentes que se repetem ciclicamente,",
                "mas a velocidade continua aumentando."
            ]
        },
        {
            "title": "Itens e Power-ups",
            "text": [
                "Pulo Duplo: Permite um segundo pulo.",
                "Escudo: Protege contra colisões.",
                "Prêmio Diário: O melhor jogador do dia ganha metade do pot!"
            ]
        }
    ]
    current_page = 0
    prev_button = Button(150, HEIGHT - 80, 100, 40, "Anterior", BLUE)
    next_button = Button(WIDTH - 250, HEIGHT - 80, 100, 40, "Próximo", GREEN)

    while tutorial_active:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            for button in buttons:
                if button.is_clicked(event):
                    tutorial_active = False

            if prev_button.is_clicked(event) and current_page > 0:
                current_page -= 1
            if next_button.is_clicked(event) and current_page < len(tutorial_pages)-1:
                current_page += 1

        screen.fill((30,30,60))
        page = tutorial_pages[current_page]
        title = TITLE_FONT.render(page["title"], True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 80))

        for i, line in enumerate(page["text"]):
            text = FONT.render(line, True, WHITE)
            screen.blit(text, (WIDTH//2 - text.get_width()//2, 180 + i*40))

        page_indicator = SMALL_FONT.render(f"Página {current_page+1}/{len(tutorial_pages)}", True, WHITE)
        screen.blit(page_indicator, (WIDTH//2 - page_indicator.get_width()//2, HEIGHT - 120))

        for button in buttons:
            button.draw(screen)
        if current_page > 0:
            prev_button.draw(screen)
        if current_page < len(tutorial_pages)-1:
            next_button.draw(screen)

        pygame.display.flip()

    return


class Player:
    def __init__(self):
        self.width = 50
        self.height = 50
        self.x = 100
        self.y = HEIGHT - self.height - 50
        self.vel_y = 0
        self.on_ground = True
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.color = BLUE
        self.jumps_available = 1
        self.shield_active = False
        self.trail = []

    def jump(self):
        if self.on_ground:
            self.vel_y = BASE_JUMP_POWER
            self.on_ground = False
            self.jumps_available = 0
            jump_sound.play()
            return [Particle(self.x + self.width//2, self.y + self.height, (150,150,150), size=random.randint(2,4)) for _ in range(10)]
        elif self.jumps_available > 0:
            self.vel_y = BASE_JUMP_POWER * 0.8
            self.jumps_available -= 1
            jump_sound.play()
            return [Particle(self.x + self.width//2, self.y + self.height//2, (100,150,255), size=random.randint(2,4)) for _ in range(8)]
        return []

    def update(self):
        self.vel_y += GRAVITY
        self.y += self.vel_y
        if self.y >= HEIGHT - self.height - 50:
            self.y = HEIGHT - self.height - 50
            self.vel_y = 0
            self.on_ground = True
            self.jumps_available = 1
        self.rect.topleft = (self.x, self.y)
        self.trail.append((self.x, self.y))
        if len(self.trail) > 20:
            self.trail.pop(0)

    def draw(self, surface):
        for i, pos in enumerate(self.trail):
            alpha = int(255 * (i+1) / len(self.trail))
            trail_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.circle(trail_surf, (*self.color, alpha), (self.width//2, self.height//2), self.width//2)
            surface.blit(trail_surf, pos)

        pygame.draw.rect(surface, self.color, self.rect, border_radius=8)
        if self.shield_active:
            pygame.draw.ellipse(surface, ORANGE, (self.x - 5, self.y - 5, self.width + 10, self.height + 10), 3)


class Obstacle:
    def __init__(self):
        self.width = random.randint(20, 50)
        self.height = random.randint(20, 70)
        self.x = WIDTH
        self.y = HEIGHT - self.height - 50
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self, current_speed):
        self.x -= current_speed
        self.rect.topleft = (self.x, self.y)

    def draw(self, surface):
        pygame.draw.rect(surface, RED, self.rect, border_radius=4)


def game_loop(username):
    global daily_pot, daily_winner, BASE_OBSTACLE_SPEED
    player = Player()
    obstacles = []
    spawn_timer = 0
    score = 0
    game_over = False
    current_speed = BASE_OBSTACLE_SPEED
    shield_timer = 0
    cheat_detected = False

    user = db_get_user(username)
    if not user:
        show_message("Usuário não existe no BD!", "Pressione ENTER para sair.")
        return None

    # Verifica saldo
    if user["balance"] < PLAY_COST:
        show_message("Saldo insuficiente para jogar!", "Pressione ENTER para voltar ao MENU")
        return None

    # Deduz o custo e atualiza no BD
    user["balance"] -= PLAY_COST
    db_update_user(user)

    daily_pot += PLAY_COST

    session_start = pygame.time.get_ticks()
    try:
        mixer.music.load('')
        mixer.music.play(-1)
    except:
        pass

    while True:
        clock.tick(FPS)

        # Anti-cheat
        elapsed_time = (pygame.time.get_ticks() - session_start) / 1000
        if elapsed_time > 0 and score / elapsed_time > 5:
            cheat_detected = True
            game_over = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if game_over:
                        return score if not cheat_detected else "cheat"
                    else:
                        _ = player.jump()
                if event.key == pygame.K_x:
                    if user["shield"] > 0 and not player.shield_active:
                        user["shield"] -= 1
                        db_update_user(user)
                        player.shield_active = True
                        shield_timer = 120
                        powerup_sound.play()
                if event.key == pygame.K_d:
                    return "end_day"

        if not game_over:
            player.update()
            if player.shield_active:
                shield_timer -= 1
                if shield_timer <= 0:
                    player.shield_active = False

            current_speed = BASE_OBSTACLE_SPEED + score * 0.05
            spawn_threshold = max(60, 90 - score // 2)
            spawn_timer += 1
            if spawn_timer > spawn_threshold:
                obstacles.append(Obstacle())
                spawn_timer = 0

            for obstacle in obstacles[:]:
                obstacle.update(current_speed)
                if obstacle.x + obstacle.width < 0:
                    obstacles.remove(obstacle)
                    score += 1
                    point_sound.play()

            for obstacle in obstacles:
                if not player.shield_active and player.rect.colliderect(obstacle.rect):
                    collision_sound.play()
                    game_over = True

            # Se o score atual for maior que daily_score do BD, atualiza
            if score > user["daily_score"]:
                user["daily_score"] = score
                db_update_user(user)
                # Atualiza daily_winner em memória
                if daily_winner is None or score > daily_winner[1]:
                    daily_winner = (username, score)

        draw_background(screen, score)
        player.draw(screen)
        for obstacle in obstacles:
            obstacle.draw(screen)

        score_text = FONT.render(f"Score: {score}", True, BLACK)
        bal_text = FONT.render(f"Saldo: {user['balance']}", True, BLACK)
        pot_text = FONT.render(f"Pot: {daily_pot}", True, BLACK)
        screen.blit(score_text, (10, 10))
        screen.blit(bal_text, (10, 40))
        screen.blit(pot_text, (10, 70))

        if game_over:
            if cheat_detected:
                over_text = FONT.render("Cheating detected! Press SPACE to finish.", True, RED)
            else:
                over_text = FONT.render("Game Over! Press SPACE to finish.", True, BLACK)
            screen.blit(over_text, (20, HEIGHT//2 - 20))

        pygame.display.flip()

    mixer.music.stop()


def end_of_day():
    global daily_pot, daily_winner, owner_balance
    if daily_winner:
        winner_name, winner_score = daily_winner
        # Carrega do BD
        user = db_get_user(winner_name)
        if user:
            reward = daily_pot // 2
            user["balance"] += reward
            db_update_user(user)

            owner_balance += daily_pot - reward

            message = (
                f"Fim do dia!\n"
                f"Vencedor: {winner_name} ({winner_score})\n"
                f"Recebeu: {reward} créditos\n"
                f"Dono: {daily_pot - reward} créditos"
            )
            show_message(message, "Pressione ENTER para voltar ao MENU")
        else:
            show_message("Vencedor não encontrado no BD.", "Pressione ENTER para voltar ao MENU")
    else:
        show_message("Fim do dia! Nenhum score registrado.", "Pressione ENTER para voltar ao MENU")

    daily_pot = 0
    daily_winner = None

    # Zera daily_score de todo mundo
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET daily_score = 0;")
            conn.commit()


def main():
    db_init()
    username = login_screen()
    while True:
        selection = main_menu(username)
        if selection == "jogar":
            result = game_loop(username)
            if result is None:
                show_message("Saldo insuficiente!", "Pressione ENTER para voltar ao MENU")
                continue
            if result == "end_day":
                end_of_day()
            elif result == "cheat":
                show_message("Cheating detected! Session terminated.", "Pressione ENTER para voltar ao MENU")
            else:
                # Salva score no BD
                db_save_score(username, result)

                # Atualiza high_score no BD
                user = db_get_user(username)
                if user and result > user["high_score"]:
                    user["high_score"] = result
                    db_update_user(user)

                show_message(f"Fim da sessão.\nSeu Score: {result}", "Pressione ENTER para voltar ao MENU")

        elif selection == "loja":
            shop_screen(username)
        elif selection == "ranking":
            ranking_screen()
        elif selection == "como jogar":
            tutorial_screen()
        elif selection == "sair":
            pygame.quit()
            sys.exit()


if __name__ == "__main__":
    main()
