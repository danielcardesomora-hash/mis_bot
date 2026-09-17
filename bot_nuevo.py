import telebot
from datetime import datetime, timezone, timedelta
import sqlite3
import threading
import time
from telebot import types
import requests
import random

# CONFIGURA TUS CREDENCIALES AQUÍ
TOKEN = "8951894759:AAEct0-KXqCufGz1sWeKHRN4hVG5yYQuoZ0"
FOOTBALL_API_KEY = "451fc328432340aa8b8e0d496e6c75a2"
ODDS_API_KEY = "01500e26b4cb2a88b63043d0f29c2a6a"         # Clave de The Odds API
ADMIN_ID = 5922391451                         # Tu ID personal de Telegram
GRUPO_TICKETS_ID = "-1003790687852"           # ID de tu grupo público para tickets
ENLACE_GRUPO_TICKETS = "https://t.me/+kzqhhn3ohSw0ZWIx"  # ENLACE DE INVITACIÓN AL GRUPO

# CONFIGURACIÓN DE ZONA HORARIA
ZONA_HORARIA_OFFSET = timedelta(hours=-4)

bot = telebot.TeleBot(TOKEN, parse_mode=None, threaded=True)
MODO_MANTENIMIENTO = False

# CACHÉ INTELIGENTE PARA THE ODDS API (Duración de 40 minutos)
cache_odds_api = {}
TIEMPO_CACHE_ODDS = 40 * 60

def limpiar_markdown(texto):
    """Limpia caracteres especiales para evitar errores de parseo en Markdown de Telegram"""
    if not texto:
        return "Usuario"
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        texto = texto.replace(char, '')
    return texto

def obtener_partidos_con_cache(sport_key):
    ahora = time.time()
    if sport_key in cache_odds_api:
        datos_guardados, timestamp = cache_odds_api[sport_key]
        if ahora - timestamp < TIEMPO_CACHE_ODDS:
            return datos_guardados

    eventos = obtener_partidos_y_cuotas_odds_api(sport_key)
    if eventos:
        cache_odds_api[sport_key] = (eventos, ahora)
    return eventos

# ==================== VERIFICACIÓN DE FRANJAS HORARIAS DEPORTIVAS ====================
def horario_deportivo_valido():
    ahora_local = datetime.now(timezone.utc) + ZONA_HORARIA_OFFSET
    hora_actual = ahora_local.time()
    
    bloque_1_inicio = datetime.strptime("08:00:00", "%H:%M:%S").time()
    bloque_1_fin = datetime.strptime("12:00:00", "%H:%M:%S").time()
    bloque_2_inicio = datetime.strptime("18:00:00", "%H:%M:%S").time()
    bloque_2_fin = datetime.strptime("22:00:00", "%H:%M:%S").time()

    en_bloque_1 = bloque_1_inicio <= hora_actual <= bloque_1_fin
    en_bloque_2 = bloque_2_inicio <= hora_actual <= bloque_2_fin
    
    return en_bloque_1 or en_bloque_2

# ==================== CONVERSIÓN DE HORA LOCAL ====================
def convertir_a_hora_local(commence_time_str):
    try:
        if commence_time_str.endswith("Z"):
            commence_time_str = commence_time_str[:-1] + "+00:00"
        dt_utc = datetime.fromisoformat(commence_time_str)
        dt_local = dt_utc + ZONA_HORARIA_OFFSET
        return dt_local.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return commence_time_str[:16].replace("T", " ")

# ==================== CONTROL ANTI-SPAM (RATE LIMITING) ====================
control_flood = {}
TIEMPO_ESPERA_MENSAJES = 1.0

def es_flood(user_id):
    if user_id == ADMIN_ID:
        return False
    ahora = time.time()
    ultimo_tiempo = control_flood.get(user_id, 0)
    if ahora - ultimo_tiempo < TIEMPO_ESPERA_MENSAJES:
        return True
    control_flood[user_id] = ahora
    return False

# ==================== VERIFICACIÓN DE SUSCRIPCIÓN AL GRUPO ====================
def verificar_suscripcion(user_id):
    str_grupo = str(GRUPO_TICKETS_ID)
    if not str_grupo or "X" in str_grupo:
        return True
    try:
        member = bot.get_chat_member(int(str_grupo), user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
    except Exception as e:
        print(f"Error al verificar suscripción: {e}")
    return False

# ==================== THE ODDS API ====================
def obtener_partidos_y_cuotas_odds_api(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            eventos = response.json()
            hoy_str = (datetime.now(timezone.utc) + ZONA_HORARIA_OFFSET).strftime("%Y-%m-%d")
            eventos_hoy = [e for e in eventos if e.get("commence_time", "").startswith(hoy_str)]
            return eventos_hoy
        else:
            print(f"Error en The Odds API ({sport_key}): {response.status_code}")
            return []
    except Exception as e:
        print(f"Excepción al conectar con The Odds API ({sport_key}): {e}")
        return []

# ==================== GESTIÓN DE BASE DE DATOS SQLite ====================
def init_db():
    conn = sqlite3.connect("bot_apuestas.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            nombre TEXT,
            saldo REAL DEFAULT 0.0,
            ultimo_bono TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            match_id TEXT,
            partido_nombre TEXT,
            seleccion TEXT,
            monto REAL,
            cuota REAL,
            ganancia_potencial REAL,
            estado TEXT DEFAULT 'PENDIENTE'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_apuestas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tipo TEXT,
            detalle TEXT,
            resultado TEXT,
            monto REAL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def obtener_db():
    return sqlite3.connect("bot_apuestas.db", check_same_thread=False)

def get_saldo(user_id, nombre_usuario="Usuario"):
    nombre_limpio = limpiar_markdown(nombre_usuario)
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("SELECT saldo FROM usuarios WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO usuarios (user_id, nombre, saldo, ultimo_bono) VALUES (?, ?, 100.0, '')", (user_id, nombre_limpio))
        conn.commit()
        saldo = 100.0
    else:
        saldo = row[0]
        # Actualizar nombre por si cambió en Telegram
        cursor.execute("UPDATE usuarios SET nombre = ? WHERE user_id = ?", (nombre_limpio, user_id))
        conn.commit()
    conn.close()
    return saldo

def actualizar_saldo(user_id, monto_sumar):
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?", (monto_sumar, user_id))
    conn.commit()
    conn.close()

estados_usuario = {}
cache_nombres_partidos = {}
CUOTAS_DINAMICAS = {}

LIGAS_ODDS_API = {
    "Premier League": "soccer_epl",
    "E S LaLiga": "soccer_spain_la_liga",
    "IT Serie A": "soccer_italy_serie_a",
    "D E Bundesliga": "soccer_germany_bundesliga",
    "Ligue 1": "soccer_france_ligue_one"
}

def borrar_mensaje_seguro(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass

def obtener_resultado_mlb(game_pk):
    try:
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None, None, False
        data = r.json()
        estado = data.get("gameData", {}).get("status", {}).get("abstractGameState", "")
        if estado != "Final":
            return None, None, False
        teams = data.get("liveData", {}).get("linescore", {}).get("teams", {})
        home = teams.get("home", {}).get("runs")
        away = teams.get("away", {}).get("runs")
        if home is None or away is None:
            return None, None, False
        return int(home), int(away), True
    except Exception as e:
        print(f"Error resultado MLB: {e}")
        return None, None, False

def sistema_pagos_automaticos():
    while True:
        try:
            conn = obtener_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticket_id, user_id, match_id, partido_nombre, seleccion, ganancia_potencial
                FROM tickets WHERE estado = 'PENDIENTE'
            """)
            tickets_pendientes = cursor.fetchall()
            conn.close()
            
            matches_evaluados = {}
            
            for t_id, u_id, match_id, partido_nombre, seleccion, ganancia in tickets_pendientes:
                resultado_ganador = None
                home_goals = None
                away_goals = None
                
                if str(match_id).startswith("mlb_"):
                    game_pk = str(match_id).replace("mlb_", "")
                    home_runs, away_runs, finalizado = obtener_resultado_mlb(game_pk)
                    if not finalizado:
                        continue
                    home_goals, away_goals = home_runs, away_runs
                    if home_runs > away_runs:
                        resultado_ganador = "1"
                    elif home_runs == away_runs:
                        resultado_ganador = "x"
                    else:
                        resultado_ganador = "2"
                else:
                    if match_id not in matches_evaluados:
                        url = f"https://api.football-data.org/v4/matches/{match_id}"
                        headers = {"X-Auth-Token": FOOTBALL_API_KEY}
                        r = requests.get(url, headers=headers, timeout=5)
                        if r.status_code == 200:
                            matches_evaluados[match_id] = r.json()
                        else:
                            continue
                            
                    data = matches_evaluados[match_id]
                    if data.get("status") != "FINISHED":
                        continue
                        
                    score = data.get("score", {}).get("fullTime", {})
                    home_goals = score.get("home")
                    away_goals = score.get("away")
                    if home_goals is None or away_goals is None:
                        continue
                        
                    if home_goals > away_goals:
                        resultado_ganador = "1"
                    elif home_goals == away_goals:
                        resultado_ganador = "x"
                    else:
                        resultado_ganador = "2"
                
                if resultado_ganador is None:
                    continue
                    
                conn = obtener_db()
                cursor = conn.cursor()
                if seleccion.lower() == resultado_ganador:
                    cursor.execute("UPDATE tickets SET estado = 'GANADO' WHERE ticket_id = ?", (t_id,))
                    cursor.execute("UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?", (ganancia, u_id))
                    conn.commit()
                    nuevo_saldo = get_saldo(u_id)
                    msg = (
                        f"🎉 *TICKET #{t_id} GANADOR* 🎉\n\n"
                        f"🏟 *Partido:* {partido_nombre}\n"
                        f"💰 *Premio acreditado:* ${ganancia:.2f}\n"
                        f"💵 *Nuevo saldo:* ${nuevo_saldo:.2f}"
                    )
                    bot.send_message(u_id, msg, parse_mode="Markdown")
                else:
                    cursor.execute("UPDATE tickets SET estado = 'PERDIDO' WHERE ticket_id = ?", (t_id,))
                    conn.commit()
                    msg = (
                        f"❌ *TICKET #{t_id} NO GANADOR* ❌\n\n"
                        f"🏟 *Partido:* {partido_nombre}\n"
                        f"📊 *Resultado final:* {home_goals}-{away_goals}\n"
                        f"Suerte en tu próxima apuesta."
                    )
                    bot.send_message(u_id, msg, parse_mode="Markdown")
                conn.close()
        except Exception as e:
            print(f"Error en liquidacion: {e}")
        time.sleep(180)

hilo_pagos = threading.Thread(target=sistema_pagos_automaticos, daemon=True)
hilo_pagos.start()

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    global MODO_MANTENIMIENTO
    user_id = message.from_user.id
    nombre_user = message.from_user.first_name or "Usuario"
    get_saldo(user_id, nombre_user)
    estados_usuario.pop(user_id, None)
    
    if message.chat.type == "private":
        borrar_mensaje_seguro(message.chat.id, message.message_id)
        
    if MODO_MANTENIMIENTO and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "El bot se encuentra temporalmente en *Mantenimiento*. Disculpa las molestias.", parse_mode="Markdown")
        return

    if user_id == ADMIN_ID:
        admin_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        admin_markup.row(types.KeyboardButton("💰 Recargar Cuenta a Usuario"), types.KeyboardButton("👤 Consultar Saldo de Usuario"))
        admin_markup.row(types.KeyboardButton("📋 Listar Usuarios Registrados"), types.KeyboardButton("📊 Estadísticas del Bot"))
        admin_markup.row(types.KeyboardButton("🛠 Alternar Mantenimiento"))
        admin_markup.row(types.KeyboardButton("📊 Ver Créditos de API"))
        estado_mant = "ACTIVADO (Bloqueado para usuarios)" if MODO_MANTENIMIENTO else "INACTIVO (Bot funcionando)"
        texto_admin = (
            "🛠 *PANEL DE CONTROL DE ADMINISTRADOR*\n\n"
            f"📌 *Estado:* {estado_mant}\n\n"
            "Selecciona una opción o usa comandos directos `/recargar ID_USUARIO MONTO`."
        )
        bot.send_message(message.chat.id, texto_admin, reply_markup=admin_markup, parse_mode="Markdown")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("⚽ Apostar"), types.KeyboardButton("🎰 Minijuegos 24/7"))
    markup.row(types.KeyboardButton("💰 Mi Dinero"), types.KeyboardButton("🎟 Mis Tickets"))
    markup.row(types.KeyboardButton("🏆 Tabla de Líderes"), types.KeyboardButton("🎁 Bono Diario"))
    markup.row(types.KeyboardButton("📢 Unirse al Grupo de Tickets"))
    
    texto_bienvenida = (
        "👋 *¡Bienvenido al Bot Oficial de Apuestas Deportivas y Casino!*\n\n"
        "Aquí podrás poner a prueba tus pronósticos con cuotas reales de mercado o divertirte en nuestra suite de minijuegos:\n\n"
        "🎁 *Bono Diario:* Reclama tus 100 créditos blindados cada 24 horas.\n"
        "⚽ *Apostar:* Explora los partidos de Fútbol y Béisbol (MLB).\n"
        "🎰 *Minijuegos 24/7:* Dado, Ruleta, Volado, Mayor o Menor y Slots.\n"
        "🏆 *Tabla de Líderes:* Top 10 de los mejores jugadores.\n"
        "📢 *Unirse al Grupo:* Accede a nuestro grupo público para ver los tickets.\n\n"
        "Selecciona una opción del menú inferior para comenzar:"
    )
    bot.send_message(message.chat.id, texto_bienvenida, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['recargar'])
def cmd_recargar(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "No tienes permisos de administrador.")
        return
    try:
        args = message.text.split()
        target_id = int(args[1])
        monto = float(args[2])
        actualizar_saldo(target_id, monto)
        nuevo_saldo = get_saldo(target_id)
        bot.reply_to(message, f"Saldo de `{target_id}` actualizado a **${nuevo_saldo:.2f}**.", parse_mode="Markdown")
        bot.send_message(target_id, f"Tu saldo ha sido actualizado por la administración. Nuevo saldo: **${nuevo_saldo:.2f}**.", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "⚠️ Uso incorrecto. Escribe: `/recargar ID_USUARIO MONTO`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_messages(message):
    global MODO_MANTENIMIENTO
    user_id = message.from_user.id
    
    if es_flood(user_id):
        return

    nombre_user = message.from_user.first_name or "Usuario"
    saldo_actual = get_saldo(user_id, nombre_user)
    estado = estados_usuario.get(user_id)

    if message.chat.type == "private" and message.content_type == "text":
        borrar_mensaje_seguro(message.chat.id, message.message_id)

    if MODO_MANTENIMIENTO and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "El bot está en mantenimiento.")
        return

    # ==================== BONO DIARIO BLINDADO (CORREGIDO) ====================
    if message.text == "🎁 Bono Diario":
        conn = obtener_db()
        cursor = conn.cursor()
        cursor.execute("SELECT ultimo_bono FROM usuarios WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        ultimo_reclamo = row[0] if row else ""
        conn.close()

        # Usar fecha local exacta basada en la zona horaria del bot
        hoy_str = (datetime.now(timezone.utc) + ZONA_HORARIA_OFFSET).strftime("%Y-%m-%d")
        
        if ultimo_reclamo == hoy_str:
            bot.send_message(message.chat.id, "⏳ Ya has reclamado tu bono diario hoy. Vuelve mañana.", parse_mode="Markdown")
            return

        conn = obtener_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET saldo = saldo + 100.0, ultimo_bono = ? WHERE user_id = ?", (hoy_str, user_id))
        conn.commit()
        conn.close()
        
        nuevo_saldo = get_saldo(user_id)
        bot.send_message(message.chat.id, f"🎁 ¡Has reclamado exitosamente tu bono diario de **100 créditos**!\n💵 Nuevo saldo: **${nuevo_saldo:.2f}**", parse_mode="Markdown")
        return

    # ==================== TABLA DE LÍDERES (CORREGIDA) ====================
    if message.text == "🏆 Tabla de Líderes":
        conn = obtener_db()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, saldo FROM usuarios ORDER BY saldo DESC LIMIT 10")
        top_usuarios = cursor.fetchall()
        conn.close()

        txt_top = "🏆 *TOP 10 - LÍDERES DE LA COMUNIDAD* 🏆\n\n"
        for i, (nombre, saldo) in enumerate(top_usuarios, start=1):
            medalla = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            nombre_seguro = limpiar_markdown(nombre)
            txt_top += f"{medalla} *{nombre_seguro}* — ${saldo:.2f} créditos\n"
        bot.send_message(message.chat.id, txt_top, parse_mode="Markdown")
        return

    # ==================== MINIJUEGOS 24/7 ====================
    if message.text == "🎰 Minijuegos 24/7":
        minijuegos_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        minijuegos_markup.row(types.KeyboardButton("🎲 Dado de la Suerte"), types.KeyboardButton("🎰 Ruleta del Casino"))
        minijuegos_markup.row(types.KeyboardButton("🪙 El Volado"), types.KeyboardButton("🃏 Mayor o Menor"))
        minijuegos_markup.row(types.KeyboardButton("🎰 Tragamonedas / Slots"), types.KeyboardButton("❓ Cómo Jugar"))
        minijuegos_markup.row(types.KeyboardButton("🔙 Volver"))
        bot.send_message(message.chat.id, "🎰 *Zona de Minijuegos 24/7*\nDisponibles en todo momento. Selecciona tu juego favorito:", reply_markup=minijuegos_markup, parse_mode="Markdown")
        return

    if message.text == "❓ Cómo Jugar":
        texto_ayuda = (
            "📖 *Guía de Minijuegos*\n\n"
            "• 🎲 *Dado de la Suerte:* Elige un monto, lanza el dado interactivo y gana si aciertas al número obtenido.\n"
            "• 🎰 *Ruleta del Casino:* Apuesta al color o sección y multiplica tu saldo si la bola se detiene en tu selección.\n"
            "• 🪙 *El Volado:* Elige Cara o Cruz y duplica tu inversión al instante si aciertas el lanzamiento.\n"
            "• 🃏 *Mayor o Menor:* Se genera una carta base; indica si la siguiente carta será mayor o menor.\n"
            "• 🎰 *Tragamonedas / Slots:* Gira los carretes y consigue combinaciones ganadoras o el jackpot acumulado."
        )
        bot.send_message(message.chat.id, texto_ayuda, parse_mode="Markdown")
        return

    if message.text in ["🎲 Dado de la Suerte", "🎰 Ruleta del Casino", "🪙 El Volado", "🃏 Mayor o Menor", "🎰 Tragamonedas / Slots"]:
        juego_nombre = message.text
        estados_usuario[user_id] = {"paso": "esperando_apuesta_minijuego", "juego": juego_nombre}
        
        montos_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
        montos_markup.add(
            types.KeyboardButton("10"), types.KeyboardButton("20"), types.KeyboardButton("50"), types.KeyboardButton("100"),
            types.KeyboardButton("200"), types.KeyboardButton("500"), types.KeyboardButton("1000")
        )
        montos_markup.row(types.KeyboardButton("🔙 Volver"))
        bot.send_message(message.chat.id, f"🎮 *{juego_nombre}*\nSaldo disponible: **${saldo_actual:.2f}**\n\nSelecciona o escribe el monto de tu apuesta:", reply_markup=montos_markup, parse_mode="Markdown")
        return

    if isinstance(estado, dict) and estado.get("paso") == "esperando_apuesta_minijuego":
        try:
            monto_min = float(message.text)
            if monto_min <= 0:
                bot.send_message(message.chat.id, "Ingresa un monto válido mayor a cero.")
                return
            if monto_min > saldo_actual:
                bot.send_message(message.chat.id, f"⚠️ Saldo insuficiente. Tu saldo es **${saldo_actual:.2f}**.", parse_mode="Markdown")
                return

            juego = estado["juego"]
            estados_usuario.pop(user_id, None)
            actualizar_saldo(user_id, -monto_min)

            acierto = random.choice([True, False])
            if "Dado" in juego:
                bot.send_dice(message.chat.id, emoji='🎲')
            elif "Tragamonedas" in juego:
                bot.send_dice(message.chat.id, emoji='🎰')

            if acierto:
                premio = monto_min * 2.0
                actualizar_saldo(user_id, premio)
                nuevo_s = get_saldo(user_id)
                bot.send_message(message.chat.id, f"🎉 ¡Felicidades! Ganaste en *{juego}*.\n🏆 Premio acreditado: **+${premio:.2f}**\n💵 Saldo actual: **${nuevo_s:.2f}**", parse_mode="Markdown")
            else:
                nuevo_s = get_saldo(user_id)
                bot.send_message(message.chat.id, f"❌ No hubo suerte en *{juego}*.\nPerdiste tu apuesta de ${monto_min:.2f}.\n💵 Saldo actual: **${nuevo_s:.2f}**", parse_mode="Markdown")
            
            minijuegos_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            minijuegos_markup.row(types.KeyboardButton("🎲 Dado de la Suerte"), types.KeyboardButton("🎰 Ruleta del Casino"))
            minijuegos_markup.row(types.KeyboardButton("🪙 El Volado"), types.KeyboardButton("🃏 Mayor o Menor"))
            minijuegos_markup.row(types.KeyboardButton("🎰 Tragamonedas / Slots"), types.KeyboardButton("❓ Cómo Jugar"))
            minijuegos_markup.row(types.KeyboardButton("🔙 Volver"))
            bot.send_message(message.chat.id, "¿Deseas jugar otra ronda?", reply_markup=minijuegos_markup)
            return
        except ValueError:
            bot.send_message(message.chat.id, "Ingresa un número válido para el monto.")
            return

    if message.text == "📢 Unirse al Grupo de Tickets":
        kb_grupo = types.InlineKeyboardMarkup()
        kb_grupo.add(types.InlineKeyboardButton("🔗 Ir al Grupo Oficial", url=ENLACE_GRUPO_TICKETS))
        bot.send_message(
            message.chat.id, 
            "📢 *Grupo Oficial de Tickets*\n\nHaz clic en el botón de abajo para unirte al grupo y ver todas las apuestas de la comunidad:", 
            reply_markup=kb_grupo, 
            parse_mode="Markdown"
        )
        return

    if isinstance(estado, dict) and estado.get("paso") == "esperando_monto_recarga":
        if user_id == ADMIN_ID:
            try:
                monto = float(message.text)
                target_id = estado["target_id"]
                estados_usuario.pop(user_id, None)
                actualizar_saldo(target_id, monto)
                nuevo_saldo = get_saldo(target_id)
                bot.send_message(message.chat.id, f"✅ Éxito! Saldo del usuario `{target_id}` actualizado. Nuevo saldo: **${nuevo_saldo:.2f}**.", parse_mode="Markdown")
                bot.send_message(target_id, f"Tu saldo ha sido actualizado por la administración! Nuevo saldo: **${nuevo_saldo:.2f}**.", parse_mode="Markdown")
            except ValueError:
                bot.send_message(message.chat.id, "Ingresa un número válido.")
        return

    if estado == "esperando_id_recarga":
        if user_id == ADMIN_ID:
            try:
                target_id = int(message.text)
                estados_usuario[user_id] = {"paso": "esperando_monto_recarga", "target_id": target_id}
                bot.send_message(message.chat.id, f"ID objetivo: `{target_id}`\n\nIngresa el monto a sumar (o negativo para restar):", parse_mode="Markdown")
            except ValueError:
                bot.send_message(message.chat.id, "El ID debe ser un número entero válido.")
        return

    if estado == "esperando_id_consulta":
        if user_id == ADMIN_ID:
            try:
                target_id = int(message.text)
                estados_usuario.pop(user_id, None)
                saldo_usuario = get_saldo(target_id)
                conn = obtener_db()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ?", (target_id,))
                total_tickets = cursor.fetchone()[0]
                conn.close()
                info_txt = (
                    "👤 *INFORMACIÓN DE CUENTA*\n\n"
                    f"🆔 *ID de Usuario:* `{target_id}`\n"
                    f"💰 *Saldo Actual:* ${saldo_usuario:.2f}\n"
                    f"🎟 *Total Tickets:* {total_tickets}"
                )
                bot.send_message(message.chat.id, info_txt, parse_mode="Markdown")
            except ValueError:
                bot.send_message(message.chat.id, "ID inválido, ingresa un número correcto.")
        return

    if estado == "esperando_monto_deposito":
        try:
            monto = float(message.text)
            if monto < 500:
                bot.send_message(message.chat.id, "⚠️ El monto mínimo de depósito es de **$500.00**.", parse_mode="Markdown")
                return
            estados_usuario[user_id] = {"paso": "esperando_comprobante", "monto": monto}
            texto_datos = (
                "📌 *Datos para transferir:*\n"
                f"💰 *Monto:* ${monto:.2f}\n"
                "🏦 *Tarjeta/Cuenta:* XXXX-XXXX-XXXX-XXXX\n"
                "📸 Envía la foto del comprobante para continuar."
            )
            bot.send_message(message.chat.id, texto_datos, parse_mode="Markdown")
        except ValueError:
            bot.send_message(message.chat.id, "Ingresa un monto válido en números.")
        return

    if isinstance(estado, dict) and estado.get("paso") == "esperando_comprobante":
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            monto = estado["monto"]
            estados_usuario.pop(user_id, None)
            bot.send_message(message.chat.id, "Comprobante recibido. En revisión por el administrador.")
            kb_admin = types.InlineKeyboardMarkup()
            kb_admin.add(
                types.InlineKeyboardButton("✅ Aprobar", callback_data=f"dep_ok_{user_id}_{monto}"),
                types.InlineKeyboardButton("❌ Rechazar", callback_data=f"dep_no_{user_id}")
            )
            caption = (
                "📥 *SOLICITUD DE DEPÓSITO*\n"
                f"👤 Usuario: `{user_id}`\n"
                f"💰 Monto: ${monto:.2f}"
            )
            bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=kb_admin, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "Por favor envía una *foto* del comprobante.", parse_mode="Markdown")
        return

    if estado == "esperando_monto_retiro":
        try:
            monto = float(message.text)
            if monto < 500:
                bot.send_message(message.chat.id, "⚠️ El monto mínimo de retiro es de **$500.00**.", parse_mode="Markdown")
                return
            if monto > saldo_actual:
                bot.send_message(message.chat.id, f"⚠️ Monto no válido. Tu saldo es **${saldo_actual:.2f}**.", parse_mode="Markdown")
                return
            estados_usuario[user_id] = {"paso": "esperando_datos_retiro", "monto": monto}
            bot.send_message(message.chat.id, "Escribe el número de tarjeta o cuenta de destino.", parse_mode="Markdown")
        except ValueError:
            bot.send_message(message.chat.id, "Ingresa un número válido.")
        return

    if isinstance(estado, dict) and estado.get("paso") == "esperando_datos_retiro":
        monto = estado["monto"]
        datos_pago = message.text
        estados_usuario.pop(user_id, None)
        bot.send_message(message.chat.id, f"📤 Solicitud de retiro por **${monto:.2f}** enviada.\nEl saldo se descontará cuando el administrador confirme el pago.", parse_mode="Markdown")
        kb_admin = types.InlineKeyboardMarkup()
        kb_admin.add(types.InlineKeyboardButton("✅ Marcar Pagado", callback_data=f"ret_ok_{user_id}_{monto}"))
        text_admin = (
            "📤 *SOLICITUD DE RETIRO*\n"
            f"👤 Usuario: `{user_id}`\n"
            f"💰 Monto: ${monto:.2f}\n"
            f"🏦 Cuenta: {datos_pago}"
        )
        bot.send_message(ADMIN_ID, text_admin, reply_markup=kb_admin, parse_mode="Markdown")
        return

    if isinstance(estado, dict) and estado.get("paso") == "esperando_monto_apuesta":
        try:
            monto_apuesta = float(message.text)
            if monto_apuesta <= 0:
                bot.send_message(message.chat.id, "Ingresa un monto mayor a cero.")
                return
            if monto_apuesta > saldo_actual:
                bot.send_message(message.chat.id, f"⚠️ Saldo insuficiente. Tu saldo actual es **${saldo_actual:.2f}**.", parse_mode="Markdown")
                return

            match_id = estado["match_id"]
            seleccion = estado["seleccion"]
            partido = estado["partido"]
            cuota = estado["cuota"]
            ganancia = monto_apuesta * cuota

            actualizar_saldo(user_id, -monto_apuesta)
            conn = obtener_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tickets (user_id, match_id, partido_nombre, seleccion, monto, cuota, ganancia_potencial)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, match_id, partido, seleccion, monto_apuesta, cuota, ganancia))
            conn.commit()
            ticket_id = cursor.lastrowid
            conn.close()
            estados_usuario.pop(user_id, None)

            msg_ticket = (
                f"🎟 *TICKET DE APUESTA CREADO (#{ticket_id})*\n\n"
                f"🏟 *Partido:* {partido}\n"
                f"🎯 *Selección:* {seleccion.upper()}\n"
                f"📊 *Cuota:* {cuota:.2f}\n"
                f"💵 *Apostado:* ${monto_apuesta:.2f}\n"
                f"🏆 *Ganancia Posible:* ${ganancia:.2f}\n"
                f"💰 *Saldo restante:* ${get_saldo(user_id):.2f}"
            )
            bot.send_message(message.chat.id, msg_ticket, parse_mode="Markdown")

            msg_grupo = (
                f"🔥 *NUEVA APUESTA REGISTRADA (#{ticket_id})* 🔥\n\n"
                f"👤 *Usuario ID:* `{user_id}`\n"
                f"🏟 *Partido:* {partido}\n"
                f"🎯 *Selección:* {seleccion.upper()} (Cuota: {cuota:.2f})\n"
                f"💵 *Monto en juego:* ${monto_apuesta:.2f}\n"
                f"🏆 *Premio Potencial:* ${ganancia:.2f}"
            )
            try:
                bot.send_message(GRUPO_TICKETS_ID, msg_grupo, parse_mode="Markdown")
            except Exception as e:
                print(f"Error al enviar ticket al grupo: {e}")

        except ValueError:
            bot.send_message(message.chat.id, "Ingresa un monto válido en números.")
        return

    if user_id == ADMIN_ID and message.text == "💰 Recargar Cuenta a Usuario":
        estados_usuario[user_id] = "esperando_id_recarga"
        bot.send_message(message.chat.id, "Ingresa el **ID de Telegram** del usuario a recargar.", parse_mode="Markdown")
        return

    if user_id == ADMIN_ID and message.text == "👤 Consultar Saldo de Usuario":
        estados_usuario[user_id] = "esperando_id_consulta"
        bot.send_message(message.chat.id, "Ingresa el **ID de Telegram** del usuario que deseas consultar.", parse_mode="Markdown")
        return

    # ==================== LISTADO DE USUARIOS ADMINISTRADOR (CORREGIDO) ====================
    if user_id == ADMIN_ID and message.text == "📋 Listar Usuarios Registrados":
        conn = obtener_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, nombre, saldo FROM usuarios")
        usuarios = cursor.fetchall()
        conn.close()

        if not usuarios:
            bot.send_message(message.chat.id, "No hay usuarios registrados en la base de datos.")
            return

        txt_lista = "📋 *LISTADO DE USUARIOS REGISTRADOS*\n\n"
        for u in usuarios:
            nombre_seguro = limpiar_markdown(u[1])
            txt_lista += f"• ID: `{u[0]}` | Nombre: {nombre_seguro} | Saldo: **${u[2]:.2f}**\n"
        
        # Enviar en bloques seguros sin romper markdown ni límite de caracteres
        if len(txt_lista) > 4000:
            for i in range(0, len(txt_lista), 4000):
                bot.send_message(message.chat.id, txt_lista[i:i+4000], parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, txt_lista, parse_mode="Markdown")
        return

    if user_id == ADMIN_ID and message.text == "📊 Estadísticas del Bot":
        conn = obtener_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        total_usuarios = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(saldo) FROM usuarios")
        dinero_total = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE estado = 'PENDIENTE'")
        tickets_pendientes = cursor.fetchone()[0]
        conn.close()
        stats_txt = (
            "📊 *ESTADÍSTICAS GENERALES*\n\n"
            f"👥 *Usuarios registrados:* {total_usuarios}\n"
            f"💰 *Dinero total en cuentas:* ${dinero_total:.2f}\n"
            f"🎟 *Tickets pendientes:* {tickets_pendientes}"
        )
        bot.send_message(message.chat.id, stats_txt, parse_mode="Markdown")
        return

    if user_id == ADMIN_ID and message.text == "🛠 Alternar Mantenimiento":
        MODO_MANTENIMIENTO = not MODO_MANTENIMIENTO
        estado_nuevo = "ACTIVADO (Usuarios bloqueados)" if MODO_MANTENIMIENTO else "DESACTIVADO (Bot abierto)"
        bot.send_message(message.chat.id, f"🛠 Modo mantenimiento cambiado a: **{estado_nuevo}**", parse_mode="Markdown")
        send_welcome(message)
        return

    if user_id == ADMIN_ID and message.text == "📊 Ver Créditos de API":
        url = "https://api.the-odds-api.com/v4/sports"
        params = {"apiKey": ODDS_API_KEY} 
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                restantes = response.headers.get("x-requests-remaining", "N/A")
                usados = response.headers.get("x-requests-used", "N/A")
                texto = (
                    "📊 *Estado de The Odds API*\n\n"
                    f"🟢 *Restantes:* `{restantes}` créditos\n"
                    f"🔴 *Usados:* `{usados}` créditos\n\n"
                    "*(Recuerda cambiar tu API Key si ves que los créditos están por agotarse)*"
                )
            else:
                texto = f"⚠️ Error al conectar con la API (Código: {response.status_code})."
            bot.send_message(message.chat.id, texto, parse_mode="Markdown")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error de red al verificar la API: {e}")
        return

    if message.text == "💰 Mi Dinero":
        dinero_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        dinero_markup.row(types.KeyboardButton("📥 Depositar"), types.KeyboardButton("📤 Retirar"))
        dinero_markup.row(types.KeyboardButton("🔙 Volver"))
        texto = f"💰 *Panel de dinero*\n\nID: `{user_id}`\nSaldo disponible: **${saldo_actual:.2f}**\n\n¿Qué deseas hacer?"
        bot.send_message(message.chat.id, texto, reply_markup=dinero_markup, parse_mode="Markdown")
        return

    if message.text == "🎟 Mis Tickets":
        conn = obtener_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticket_id, partido_nombre, seleccion, monto, ganancia_potencial, estado
            FROM tickets WHERE user_id = ? ORDER BY ticket_id DESC LIMIT 5
        """, (user_id,))
        tickets = cursor.fetchall()
        conn.close()
        if not tickets:
            bot.send_message(message.chat.id, "Aún no tienes tickets de apuestas realizados.")
            return
        txt = "🎟 *TUS ÚLTIMOS TICKETS:*\n\n"
        for t in tickets:
            txt += f"• *Ticket #{t[0]}* — {t[1]}\n  Opción: {t[2].upper()} | ${t[3]:.2f} → **${t[4]:.2f}** | {t[5]}\n\n"
        bot.send_message(message.chat.id, txt, parse_mode="Markdown")
        return

    if message.text == "📥 Depositar":
        estados_usuario[user_id] = "esperando_monto_deposito"
        bot.send_message(message.chat.id, "Ingresa el monto a depositar.")
        return

    if message.text == "📤 Retirar":
        if saldo_actual <= 0:
            bot.send_message(message.chat.id, "No tienes saldo disponible.")
        else:
            estados_usuario[user_id] = "esperando_monto_retiro"
            bot.send_message(message.chat.id, f"Ingresa el monto a retirar (Disponible: **${saldo_actual:.2f}**).", parse_mode="Markdown")
        return

    # ==================== APUESTAS DEPORTIVAS ====================
    if message.text == "⚽ Apostar":
        if not horario_deportivo_valido() and user_id != ADMIN_ID:
            bot.send_message(
                message.chat.id, 
                "🔒 *Mercado Deportivo Cerrado*\n\nLas apuestas deportivas solo están habilitadas en las franjas horarias de **08:00 AM a 12:00 PM** y de **06:00 PM a 10:00 PM**.\n\n💡 *Recuerda que puedes usar la sección de Minijuegos 24/7 en cualquier momento.*", 
                parse_mode="Markdown"
            )
            return

        sub_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        hay_futbol = False
        for sport_key in LIGAS_ODDS_API.values():
            if obtener_partidos_con_cache(sport_key):
                hay_futbol = True
                break
        hay_beisbol = bool(obtener_partidos_con_cache("baseball_mlb"))

        if hay_futbol:
            sub_markup.row(types.KeyboardButton("⚽ Fútbol"))
        if hay_beisbol:
            sub_markup.row(types.KeyboardButton("🏀 Pelota"))
            
        sub_markup.row(types.KeyboardButton("🔙 Volver"))
        
        if not hay_futbol and not hay_beisbol:
            bot.send_message(message.chat.id, "⚠️ No hay partidos programados para hoy en ningún deporte.", reply_markup=sub_markup)
        else:
            bot.send_message(message.chat.id, "Selecciona el deporte disponible para hoy:", reply_markup=sub_markup)
        return

    if message.text == "⚽ Fútbol":
        ligas_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        contador_ligas = 0
        
        for nombre_liga, sport_key in LIGAS_ODDS_API.items():
            partidos_liga = obtener_partidos_con_cache(sport_key)
            if partidos_liga and len(partidos_liga) > 0:
                ligas_markup.row(types.KeyboardButton(nombre_liga))
                contador_ligas += 1
                
        ligas_markup.row(types.KeyboardButton("🔙 Volver"))
        
        if contador_ligas == 0:
            bot.send_message(message.chat.id, "⚠️ Hoy no hay partidos programados en ninguna liga de fútbol.", reply_markup=ligas_markup)
        else:
            bot.send_message(message.chat.id, "⚽ *Ligas de Fútbol con partidos hoy:*", reply_markup=ligas_markup, parse_mode="Markdown")
        return

    if message.text == "🏀 Pelota":
        pelota_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        pelota_markup.row(types.KeyboardButton("⚾ MLB"))
        pelota_markup.row(types.KeyboardButton("🔙 Volver"))
        bot.send_message(message.chat.id, "🏀 *Sección Pelota (Cuotas Reales)*\nSelecciona la liga de béisbol:", reply_markup=pelota_markup, parse_mode="Markdown")
        return

    if message.text == "⚾ MLB":
        bot.send_message(message.chat.id, "⏳ Consultando partidos de MLB para hoy...")
        partidos = obtener_partidos_con_cache("baseball_mlb")
        if not partidos:
            bot.send_message(message.chat.id, "⚠️ No hay partidos de MLB programados para hoy.")
            return

        for evento in partidos[:12]:
            local = evento["home_team"]
            visita = evento["away_team"]
            match_id = f"mlb_{evento['id']}"
            
            fecha_utc = evento.get("commence_time", "")
            fecha = convertir_a_hora_local(fecha_utc)
            
            bookmakers = evento.get("bookmakers", [])
            cuota_1, cuota_x, cuota_2 = 1.90, 3.30, 2.10
            
            if bookmakers:
                for m in bookmakers[0].get("markets", []):
                    if m.get("key") == "h2h":
                        for o in m.get("outcomes", []):
                            if o.get("name") == local:
                                cuota_1 = o.get("price", 1.90)
                            elif o.get("name") == visita:
                                cuota_2 = o.get("price", 2.10)
                            elif o.get("name") in ["Draw", "Empate"]:
                                cuota_x = o.get("price", 3.30)

            cache_nombres_partidos[match_id] = f"{local} vs {visita}"
            CUOTAS_DINAMICAS[f"{match_id}_1"] = cuota_1
            CUOTAS_DINAMICAS[f"{match_id}_x"] = cuota_x
            CUOTAS_DINAMICAS[f"{match_id}_2"] = cuota_2

            inline_kb = types.InlineKeyboardMarkup()
            inline_kb.add(
                types.InlineKeyboardButton(f"1 ({cuota_1})", callback_data=f"ap_{match_id}_1"),
                types.InlineKeyboardButton(f"X ({cuota_x})", callback_data=f"ap_{match_id}_x"),
                types.InlineKeyboardButton(f"2 ({cuota_2})", callback_data=f"ap_{match_id}_2")
            )
            texto_partido = (
                f"⚾ *{local} vs {visita}*\n"
                f"🕒 Hora Local: `{fecha}`\n"
                f"📊 *Cuotas Reales:* Local `{cuota_1}` | Empate `{cuota_x}` | Visitante `{cuota_2}`"
            )
            bot.send_message(message.chat.id, texto_partido, reply_markup=inline_kb, parse_mode="Markdown")
        return

    if message.text in LIGAS_ODDS_API:
        sport_key = LIGAS_ODDS_API[message.text]
        bot.send_message(message.chat.id, f"⏳ Consultando todos los partidos de {message.text} para hoy...")
        partidos = obtener_partidos_con_cache(sport_key)
        if not partidos:
            bot.send_message(message.chat.id, "⚠️ No hay partidos programados para hoy en esta liga.")
            return

        for evento in partidos[:12]:
            local = evento["home_team"]
            visita = evento["away_team"]
            match_id = str(evento["id"])
            
            fecha_utc = evento.get("commence_time", "")
            fecha = convertir_a_hora_local(fecha_utc)
            
            bookmakers = evento.get("bookmakers", [])
            cuota_1, cuota_x, cuota_2 = 1.90, 3.30, 2.10
            
            if bookmakers:
                for m in bookmakers[0].get("markets", []):
                    if m.get("key") == "h2h":
                        for o in m.get("outcomes", []):
                            if o.get("name") == local:
                                cuota_1 = o.get("price", 1.90)
                            elif o.get("name") == visita:
                                cuota_2 = o.get("price", 2.10)
                            elif o.get("name") in ["Draw", "Empate"]:
                                cuota_x = o.get("price", 3.30)

            cache_nombres_partidos[match_id] = f"{local} vs {visita}"
            CUOTAS_DINAMICAS[f"{match_id}_1"] = cuota_1
            CUOTAS_DINAMICAS[f"{match_id}_x"] = cuota_x
            CUOTAS_DINAMICAS[f"{match_id}_2"] = cuota_2

            inline_kb = types.InlineKeyboardMarkup()
            inline_kb.add(
                types.InlineKeyboardButton(f"1 ({cuota_1})", callback_data=f"ap_{match_id}_1"),
                types.InlineKeyboardButton(f"X ({cuota_x})", callback_data=f"ap_{match_id}_x"),
                types.InlineKeyboardButton(f"2 ({cuota_2})", callback_data=f"ap_{match_id}_2")
            )
            texto_partido = (
                f"⚽ *{local} vs {visita}*\n"
                f"🕒 Hora Local: `{fecha}`\n"
                f"📊 *Cuotas Reales:* Local `{cuota_1}` | Empate `{cuota_x}` | Visitante `{cuota_2}`"
            )
            bot.send_message(message.chat.id, texto_partido, reply_markup=inline_kb, parse_mode="Markdown")
        return

    if message.text == "🔙 Volver":
        if estado in ("esperando_monto_deposito", "esperando_monto_retiro") or (isinstance(estado, dict) and estado.get("paso") in ("esperando_datos_retiro", "esperando_comprobante", "esperando_apuesta_minijuego")):
            estados_usuario.pop(user_id, None)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(types.KeyboardButton("⚽ Apostar"), types.KeyboardButton("🎰 Minijuegos 24/7"))
        markup.row(types.KeyboardButton("💰 Mi Dinero"), types.KeyboardButton("🎟 Mis Tickets"))
        markup.row(types.KeyboardButton("🏆 Tabla de Líderes"), types.KeyboardButton("🎁 Bono Diario"))
        markup.row(types.KeyboardButton("📢 Unirse al Grupo de Tickets"))
        bot.send_message(message.chat.id, "Has vuelto al menú principal.", reply_markup=markup)
        return

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = call.data
    user_id = call.from_user.id

    if data.startswith("dep_ok_"):
        partes = data.split("_")
        target_user_id = int(partes[2])
        monto = float(partes[3])
        actualizar_saldo(target_user_id, monto)
        nuevo_saldo = get_saldo(target_user_id)
        bot.answer_callback_query(call.id, "✅ Depósito aprobado")
        bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=f"✅ *DEPÓSITO APROBADO* (${monto:.2f})", parse_mode="Markdown")
        bot.send_message(target_user_id, f"Tu depósito de **${monto:.2f}** ha sido aprobado! Saldo: **${nuevo_saldo:.2f}**.", parse_mode="Markdown")

    elif data.startswith("dep_no_"):
        target_user_id = int(data.split("_")[2])
        bot.answer_callback_query(call.id, "❌ Depósito rechazado")
        bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption="❌ *DEPÓSITO RECHAZADO*", parse_mode="Markdown")
        bot.send_message(target_user_id, "❌ Tu solicitud de depósito ha sido rechazada.")

    elif data.startswith("ret_ok_"):
        partes = data.split("_")
        target_user_id = int(partes[2])
        monto = float(partes[3])
        saldo_actual = get_saldo(target_user_id)

        if saldo_actual < monto:
            bot.answer_callback_query(call.id, "⚠️ El usuario ya no tiene saldo suficiente.", show_alert=True)
            bot.edit_message_text("⚠️ *RETIRO NO PROCESADO*\nSaldo insuficiente.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
            return

        actualizar_saldo(target_user_id, -monto)
        nuevo_saldo = get_saldo(target_user_id)
        bot.answer_callback_query(call.id, "✅ Retiro procesado")
        bot.edit_message_text(f"✅ *RETIRO COMPLETADO Y PAGADO* (${monto:.2f})", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
        bot.send_message(target_user_id, f"✅ Tu retiro de **${monto:.2f}** ha sido procesado y pagado.\nNuevo saldo: **${nuevo_saldo:.2f}**.", parse_mode="Markdown")

    elif data.startswith("ap_"):
        if not horario_deportivo_valido() and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⚠️ El mercado deportivo se encuentra cerrado en este horario.", show_alert=True)
            return

        if not verificar_suscripcion(user_id):
            bot.answer_callback_query(
                call.id, 
                "⚠️ Debes unirte a nuestro grupo de tickets para poder apostar.", 
                show_alert=True
            )
            return

        resto = data[3:]
        ultimo_guion = resto.rfind("_")
        match_id = resto[:ultimo_guion]
        seleccion = resto[ultimo_guion + 1:]

        partido_nombre = cache_nombres_partidos.get(match_id, "Partido desconocido")
        cuota = CUOTAS_DINAMICAS.get(data[3:], 2.00)
        saldo = get_saldo(user_id)

        if saldo <= 0:
            bot.answer_callback_query(call.id, "⚠️ Saldo insuficiente para apostar.", show_alert=True)
            return

        estados_usuario[user_id] = {
            "paso": "esperando_monto_apuesta",
            "match_id": match_id,
            "partido": partido_nombre,
            "seleccion": seleccion,
            "cuota": cuota
        }
        msg_confirm = (
            f"🎯 *Opción seleccionada:* {seleccion.upper()}\n"
            f"📊 *Cuota Real:* {cuota:.2f}\n"
            f"🏟 *Partido:* {partido_nombre}\n"
            f"💰 *Tu saldo:* ${saldo:.2f}\n\n"
            "✍️ Escribe el monto que deseas apostar:"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, msg_confirm, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot corriendo con los fallos del bono, tabla de líderes y panel de admin corregidos...")
    bot.infinity_polling()
