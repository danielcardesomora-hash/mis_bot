import telebot
from telebot import types
import json
import os
import random
import time
from datetime import datetime

# ================= CONFIGURACIÓN Y SEGURIDAD =================
TOKEN = '8815523653:AAFbDwVgPq7W8Q4VBj2hvgk7zaai5jW_1KI'  # Reemplaza con tu token de BotFather
ADMIN_ID = 5922391451     # Reemplaza con tu ID numérico de administrador

bot = telebot.TeleBot(TOKEN)
DB_FILE = 'database.json'

# Diccionario temporal para guardar la última acción y el monto del jugador
APUESTAS_TEMPORALES = {}

# ================= GESTIÓN DE BASE DE DATOS LOCAL =================
def cargar_datos():
    if not os.path.exists(DB_FILE):
        return {"usuarios": {}, "cupones": {}, "duelos": {}}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            datos = json.load(f)
            if "usuarios" not in datos:
                datos = {"usuarios": datos, "cupones": {}, "duelos": {}}
            if "duelos" not in datos:
                datos["duelos"] = {}
            if "cupones" not in datos:
                datos["cupones"] = {}
            return datos
    except Exception:
        return {"usuarios": {}, "cupones": {}, "duelos": {}}

def guardar_datos(datos):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar base de datos: {e}")

def obtener_rango(partidas, victorias):
    if partidas < 10:
        return "Novato 🎲"
    elif partidas < 30 or victorias < 10:
        return "Jugador Regular 🎯"
    else:
        return "High Roller 🔥"

def obtener_usuario(user_id, username=""):
    db = cargar_datos()
    usuarios = db["usuarios"]
    str_id = str(user_id)
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    if str_id not in usuarios:
        usuarios[str_id] = {
            "username": username,
            "saldo": 200,
            "retiro_hoy": 0,
            "fecha_retiro": hoy,
            "ultimo_bono": 0,
            "pendiente_deposito": 0,
            "pendiente_retiro": 0,
            "banned": False,
            "referidos": 0,
            "partidas_jugadas": 0,
            "victorias": 0,
            "titulo": "Novato 🎲",
            "multiplicador_ganancia": 1.0,
            "fecha_misiones": hoy,
            "mision_juegos": 0,
            "mision_victorias": 0,
            "recompensa_mision_1": False,
            "recompensa_mision_2": False,
            "membresia_activa": None,
            "membresia_vencimiento": 0,
            "ultimo_cobro_membresia": 0,
            "horas_actividad": 0.0
        }
        guardar_datos(db)
    else:
        user = usuarios[str_id]
        user["titulo"] = obtener_rango(user.get("partidas_jugadas", 0), user.get("victorias", 0))
        
        if user.get("fecha_misiones") != hoy:
            user["fecha_misiones"] = hoy
            user["mision_juegos"] = 0
            user["mision_victorias"] = 0
            user["recompensa_mision_1"] = False
            user["recompensa_mision_2"] = False
            guardar_datos(db)

        if user.get("fecha_retiro") != hoy:
            user["fecha_retiro"] = hoy
            user["retiro_hoy"] = 0
            guardar_datos(db)
            
    return usuarios[str_id]

def actualizar_campo(user_id, campo, valor):
    db = cargar_datos()
    str_id = str(user_id)
    if str_id in db["usuarios"]:
        db["usuarios"][str_id][campo] = valor
        guardar_datos(db)

def registrar_partida(user_id, gano=False):
    db = cargar_datos()
    str_id = str(user_id)
    if str_id in db["usuarios"]:
        u = db["usuarios"][str_id]
        u["partidas_jugadas"] += 1
        u["mision_juegos"] = u.get("mision_juegos", 0) + 1
        u["horas_actividad"] = round(u.get("horas_actividad", 0.0) + 0.1, 2)
        if gano:
            u["victorias"] += 1
            u["mision_victorias"] = u.get("mision_victorias", 0) + 1
        guardar_datos(db)

# ================= COMANDO /START Y PANELES REORGANIZADOS =================
@bot.message_handler(commands=['start'])
def enviar_bienvenida(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_id = args[1].replace("ref_", "")
        db = cargar_datos()
        if ref_id != str(user_id) and ref_id in db["usuarios"]:
            str_id = str(user_id)
            if str_id not in db["usuarios"]:
                db["usuarios"][ref_id]["referidos"] += 1
                db["usuarios"][ref_id]["saldo"] += 200
                guardar_datos(db)
                try:
                    bot.send_message(int(ref_id), f"🎉 ¡Alguien usó tu enlace de invitado! Recibiste **+200 fichas**.", parse_mode="Markdown")
                except Exception:
                    pass
    enviar_bienvenida_segun_rol(message)

def enviar_bienvenida_segun_rol(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Sin usuario"
    user_data = obtener_usuario(user_id, username)

    if user_data.get("banned", False):
        bot.reply_to(message, "❌ Tu cuenta ha sido bloqueada por un administrador.")
        return

    if user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(
            types.KeyboardButton('🛠️ Panel Admin'),
            types.KeyboardButton('👤 Ver Menú de Usuario (Temporal)'),
            types.KeyboardButton('🧹 Limpiar Pantalla')
        )
        bot.send_message(message.chat.id, "👑 **Panel de Control de Administrador**\nBienvenido, jefe. Selecciona una opción:", reply_markup=markup, parse_mode="Markdown")
        return

    enviar_menu_usuario(message.chat.id, user_data)

def enviar_menu_usuario(chat_id, user_data):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('🎰 Zona de Juegos 🎮'),
        types.KeyboardButton('💰 Ver Saldo 🪙'),
        types.KeyboardButton('📊 Mi Perfil 👤'),
        types.KeyboardButton('🎁 Bono Diario ✨'),
        types.KeyboardButton('📜 Misiones Diarias 🎯'),
        types.KeyboardButton('⚔️ Duelos PvP 🎲'),
        types.KeyboardButton('🏆 Top Jugadores 👑'),
        types.KeyboardButton('🛍️ Tienda de Títulos 🏷️'),
        types.KeyboardButton('💎 Membresías VIP 🌟'),
        types.KeyboardButton('👥 Referidos 🔗'),
        types.KeyboardButton('🎟️ Canjear Cupón 🔖'),
        types.KeyboardButton('💵 Depositar 💳'),
        types.KeyboardButton('💸 Retirar 🏧'),
        types.KeyboardButton('❓ Ayuda General 💡'),
        types.KeyboardButton('🧹 Limpiar Pantalla 🧽')
    )
    bot.send_message(chat_id, f"🎰✨ **¡Bienvenido al Casino VIP!** ✨🎰\n💰 Tu saldo actual: **${user_data['saldo']}** fichas.\n\n🔥 *¡Selecciona tu juego y revienta la banca!*", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['clean'])
def comando_clean(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Sin usuario"
    user_data = obtener_usuario(user_id, username)
    if user_data.get("banned", False):
        return
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    enviar_bienvenida_segun_rol(message)

# ================= MANEJADOR DE MENÚS Y ACCIONES =================
@bot.message_handler(func=lambda message: True)
def manejar_mensajes(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Sin usuario"
    user_data = obtener_usuario(user_id, username)

    if user_data.get("banned", False):
        return

    texto = message.text

    if texto in ['🧹 Limpiar Pantalla', '🧹 Limpiar Pantalla 🧽']:
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
        enviar_bienvenida_segun_rol(message)
        return

    if texto == '👤 Ver Menú de Usuario (Temporal)' and user_id == ADMIN_ID:
        enviar_menu_usuario(message.chat.id, user_data)
        return

    if texto == '🛠️ Panel Admin' and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 Gestionar Depósitos/Retiros", callback_data="admin_pagos"),
            types.InlineKeyboardButton("➕ Dar Fichas", callback_data="admin_dar"),
            types.InlineKeyboardButton("➖ Quitar Fichas", callback_data="admin_quitar"),
            types.InlineKeyboardButton("📊 Estadísticas Globales", callback_data="admin_stats"),
            types.InlineKeyboardButton("📢 Enviar Anuncio (Broadcast)", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("🚫 Banear / Desbloquear Usuario", callback_data="admin_ban"),
            types.InlineKeyboardButton("🎟️ Crear Cupón", callback_data="admin_cupon")
        )
        bot.reply_to(message, "🛠️ **Panel de Administración**", reply_markup=markup, parse_mode="Markdown")
        return

    user_data["horas_actividad"] = round(user_data.get("horas_actividad", 0.0) + 0.02, 2)
    actualizar_campo(user_id, "horas_actividad", user_data["horas_actividad"])

    if texto in ['❓ Ayuda General', '❓ Ayuda General 💡']:
        texto_ayuda = (
            "❓ **Guía y Ayuda General del Bot** ❓\n\n"
            "• **Zona de Juegos:** Elige tu minijuego favorito, mantén tus partidas fluidas con los botones de repetición y gana a lo grande.\n"
            "• **Bono Diario:** Reclama 100 fichas cada 24 horas.\n"
            "• **Misiones Diarias:** Completa juegos y victorias para obtener recompensas extra.\n"
            "• **Tienda de Títulos:** Compra títulos permanentes que mejoran tu multiplicador de ganancias.\n"
            "• **Membresías VIP:** Adquiere rangos y cobra pagos diarios.\n"
            "• **Referidos:** Invita amigos y gana 200 fichas por cada uno."
        )
        bot.reply_to(message, texto_ayuda, parse_mode="Markdown")
        return

    elif texto in ['🎰 Zona de Juegos', '🎰 Zona de Juegos 🎮']:
        mostrar_menu_juegos(message.chat.id, es_nuevo=True)
        return

    elif texto in ['⚔️ Duelos PvP', '⚔️ Duelos PvP 🎲']:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎲 Crear Reto de 100 fichas", callback_data="crear_duelo"),
            types.InlineKeyboardButton("📋 Ver Retos Disponibles", callback_data="ver_duelos")
        )
        bot.reply_to(message, "⚔️ **Zona de Duelos PvP**\nRetá a otros jugadores en un lanzamiento de dados directo.", reply_markup=markup, parse_mode="Markdown")
        return

    elif texto in ['🏆 Top Jugadores', '🏆 Top Jugadores 👑']:
        db = cargar_datos()
        usuarios = db["usuarios"]
        top_users = sorted(usuarios.items(), key=lambda x: x[1].get("saldo", 0), reverse=True)[:10]
        texto_top = "🏆 **Top 10 Jugadores Más Ricos** 🏆\n\n"
        for i, (uid, udata) in enumerate(top_users, 1):
            medalla = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            texto_top += f"{medalla} @{udata.get('username', 'Anónimo')} -  💰 `${udata.get('saldo', 0)}` ({udata.get('titulo', 'Novato')})\n"
        bot.reply_to(message, texto_top, parse_mode="Markdown")
        return

    elif texto in ['📜 Misiones Diarias', '📜 Misiones Diarias 🎯']:
        juegos = user_data.get("mision_juegos", 0)
        vics = user_data.get("mision_victorias", 0)
        m1_listo = juegos >= 5
        m2_listo = vics >= 3
        m1_reclamada = user_data.get("recompensa_mision_1", False)
        m2_reclamada = user_data.get("recompensa_mision_2", False)

        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if m1_reclamada:
            btn_m1 = types.InlineKeyboardButton("✅ Misión 1 (Ya reclamada hoy)", callback_data="mision_ya_reclamada")
        elif m1_listo:
            btn_m1 = types.InlineKeyboardButton("🎁 Reclamar Misión 1 (+150 fichas)", callback_data="reclamar_m1")
        else:
            btn_m1 = types.InlineKeyboardButton(f"⏳ Misión 1 en progreso ({juegos}/5 partidas)", callback_data="mision_en_progreso")
            
        if m2_reclamada:
            btn_m2 = types.InlineKeyboardButton("✅ Misión 2 (Ya reclamada hoy)", callback_data="mision_ya_reclamada")
        elif m2_listo:
            btn_m2 = types.InlineKeyboardButton("🎁 Reclamar Misión 2 (+250 fichas)", callback_data="reclamar_m2")
        else:
            btn_m2 = types.InlineKeyboardButton(f"⏳ Misión 2 en progreso ({vics}/3 victorias)", callback_data="mision_en_progreso")

        markup.add(btn_m1, btn_m2)

        texto_misiones = (
            f"📜 **Misiones Diarias (Se actualizan cada 24h)**\n\n"
            f"1️⃣ Juega 5 partidas ({juegos}/5): {'✅ ¡Completado!' if m1_listo else 'En progreso...'}\n"
            f"2️⃣ Consigue 3 victorias ({vics}/3): {'✅ ¡Completado!' if m2_listo else 'En progreso...'}"
        )
        bot.reply_to(message, texto_misiones, reply_markup=markup, parse_mode="Markdown")
        return

    elif texto in ['🛍️ Tienda de Títulos', '🛍️ Tienda de Títulos 🏷️']:
        mult_pct = int((user_data.get("multiplicador_ganancia", 1.0) - 1.0) * 100)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("♠️ Título: Apostador (1,000 fichas) [+1% Ganancia]", callback_data="comprar_titulo_1"),
            types.InlineKeyboardButton("🔥 Título: High Roller (5,000 fichas) [+3% Ganancia]", callback_data="comprar_titulo_2"),
            types.InlineKeyboardButton("👑 Título: Rey del Casino (15,000 fichas) [+5% Ganancia]", callback_data="comprar_titulo_3")
        )
        bot.reply_to(message, f"🛍️ **Tienda de Títulos VIP**\nTu rango actual: **{user_data.get('titulo', 'Novato')}**\nTu bono de ganancia activo: `+{mult_pct}%`\n\nElige el título que deseas comprar:", reply_markup=markup, parse_mode="Markdown")
        return

    elif texto in ['💎 Membresías VIP', '💎 Membresías VIP 🌟']:
        mostrar_menu_membresias(message.chat.id, es_nuevo=True, user_data=user_data)
        return

    elif texto in ['👥 Referidos', '👥 Referidos 🔗']:
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        cant_ref = user_data.get("referidos", 0)
        bot.reply_to(message, f"👥 **Sistema de Referidos**\nEnlace:\n`{link}`\n\n- Ganas **+200 fichas** por cada amigo.\n- Amigos invitados: **{cant_ref}**", parse_mode="Markdown")
        return

    elif texto in ['📊 Mi Perfil', '📊 Mi Perfil 👤']:
        jugadas = user_data.get("partidas_jugadas", 0)
        vics = user_data.get("victorias", 0)
        rango_actual = obtener_rango(jugadas, vics)
        bonus_pct = int((user_data.get("multiplicador_ganancia", 1.0) - 1.0) * 100)
        membresia_actual = user_data.get("membresia_activa")
        membresia_txt = membresia_actual.upper() if membresia_actual else "Ninguna"
        horas_actuales = user_data.get("horas_actividad", 0.0)

        texto_perfil = (
            f"📊 **Perfil de Usuario**\n\n"
            f"👤 Usuario: @{username}\n"
            f"💰 Saldo actual: `${user_data['saldo']}` fichas\n"
            f"🎖️ Rango: {rango_actual}\n"
            f"⚡ Bono pasivo: `+{bonus_pct}%`\n"
            f"💎 Membresía: **{membresia_txt}**\n"
            f"⏱️ Actividad: `{horas_actuales}h`\n"
            f"🎮 Partidas: {jugadas} | 🏆 Victorias: {vics}\n"
            f"👥 Referidos: {user_data.get('referidos', 0)}"
        )
        bot.reply_to(message, texto_perfil, parse_mode="Markdown")
        return

    elif texto in ['💰 Ver Saldo', '💰 Ver Saldo 🪙']:
        bot.reply_to(message, f"Tu saldo actual es de: **${user_data['saldo']}** fichas.", parse_mode="Markdown")

    elif texto in ['🎁 Bono Diario', '🎁 Bono Diario ✨']:
        tiempo_actual = time.time()
        ultimo_cobro = user_data.get("ultimo_bono", 0)
        tiempo_espera = 86400

        if tiempo_actual - ultimo_cobro < tiempo_espera:
            tiempo_restante = int(tiempo_espera - (tiempo_actual - ultimo_cobro))
            horas = tiempo_restante // 3600
            minutos = (tiempo_restante % 3600) // 60
            bot.reply_to(message, f"⏳ Ya reclamaste tu bono. Vuelve en **{horas}h {minutos}m**.", parse_mode="Markdown")
        else:
            user_data["saldo"] += 100
            user_data["ultimo_bono"] = tiempo_actual
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            actualizar_campo(user_id, 'ultimo_bono', user_data['ultimo_bono'])
            bot.reply_to(message, f"🎁 ¡Bono diario reclamado de **100 fichas**!\n💰 Saldo: **${user_data['saldo']}**", parse_mode="Markdown")

    elif texto in ['💵 Depositar', '💵 Depositar 💳']:
        msg = bot.reply_to(message, "⚠️ **Depósito**\nMínimo **500 fichas**.\nEscribe la cantidad a depositar (o /cancelar):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_deposito)

    elif texto in ['💸 Retirar', '💸 Retirar 🏧']:
        msg = bot.reply_to(message, f"⚠️ **Retiro**\n- Mínimo: 500\n- Máx diario: 10,000\n- Retirado hoy: {user_data['retiro_hoy']}\n\nEscribe la cantidad:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_retiro)

    elif texto in ['🎟️ Canjear Cupón', '🎟️ Canjear Cupón 🔖']:
        msg = bot.reply_to(message, "🎟️ Escribe el código de tu cupón:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_canje_cupon)

    else:
        bot.reply_to(message, "🤖 No reconozco esa opción. Utiliza los botones del menú inferior o escribe /clean para refrescar la pantalla.", parse_mode="Markdown")

# ================= FLUJO DINÁMICO DE JUEGOS Y APUESTAS CONTINUAS =================
def mostrar_menu_juegos(chat_id, message_id=None, es_nuevo=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🪙 Cara o Cruz", callback_data="juego_caracruz"),
        types.InlineKeyboardButton("🎲 Lanzamiento Dados", callback_data="juego_dados"),
        types.InlineKeyboardButton("🎰 Tragamonedas", callback_data="juego_slots"),
        types.InlineKeyboardButton("🎡 La Ruleta", callback_data="juego_ruleta"),
        types.InlineKeyboardButton("🃏 Blackjack Rápido", callback_data="juego_blackjack"),
        types.InlineKeyboardButton("🚀 Crash Multiplicador", callback_data="juego_crash"),
        types.InlineKeyboardButton("🎴 Baccarat", callback_data="juego_baccarat"),
        types.InlineKeyboardButton("📦 El Cofre Oculto", callback_data="juego_cofre"),
        types.InlineKeyboardButton("🐎 Carrera Caballos", callback_data="juego_caballos"),
        types.InlineKeyboardButton("🔮 Esfera de la Suerte", callback_data="juego_esfera")
    )
    texto = "🎰 ✨ **Zona de Juegos VIP** ✨ 🎰\nElige tu minijuego favorito:"
    if es_nuevo:
        bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")
    else:
        try:
            bot.edit_message_text(texto, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('juego_') and len(call.data.split('_')) == 2)
def selector_opciones_juego(call):
    juego = call.data.split('_')[1]

    if juego == 'caracruz':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🪙 CARA", callback_data="cc_sel_cara"), types.InlineKeyboardButton("🪙 CRUZ", callback_data="cc_sel_cruz"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_caracruz"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🪙 **Cara o Cruz**\n¿Por qué lado vas?", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'dados':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🔢 Par", callback_data="dado_sel_par"), types.InlineKeyboardButton("🔢 Impar", callback_data="dado_sel_impar"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_dados"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🎲 **Dados**\n¿Par o Impar?", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'slots':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎰 ¡Ir a Girar Rodillos!", callback_data="slot_sel_girar"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_slots"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🎰 **Tragamonedas**\nCombina símbolos para ganar premios.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'ruleta':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🔴 Rojo", callback_data="rul_sel_rojo"), types.InlineKeyboardButton("⚫ Negro", callback_data="rul_sel_negro"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_ruleta"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🎡 **Ruleta**\nElige un color.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'blackjack':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🃏 Pedir Carta", callback_data="bj_sel_pedir"), types.InlineKeyboardButton("🛑 Plantarse", callback_data="bj_sel_plantar"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_blackjack"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🃏 **Blackjack Rápido**\nTienes 16 puntos base.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'crash':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🚀 Retirar en 1.5x", callback_data="crash_sel_1.5"), types.InlineKeyboardButton("🚀 Arriesgar a 2.5x", callback_data="crash_sel_2.5"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_crash"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🚀 **Crash Multiplicador**\nRetira antes de la explosión.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'baccarat':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("👤 Jugador", callback_data="bac_sel_jugador"), types.InlineKeyboardButton("🏦 Banca", callback_data="bac_sel_banca"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_baccarat"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🎴 **Baccarat**\n¿Quién ganará la mano?", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'cofre':
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(types.InlineKeyboardButton("📦 1", callback_data="cofre_sel_1"), types.InlineKeyboardButton("📦 2", callback_data="cofre_sel_2"), types.InlineKeyboardButton("📦 3", callback_data="cofre_sel_3"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_cofre"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("📦 **El Cofre Oculto**\nElige un cofre con tesoro.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'caballos':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🐎 1", callback_data="cab_sel_1"), types.InlineKeyboardButton("🐎 2", callback_data="cab_sel_2"), types.InlineKeyboardButton("🐎 3", callback_data="cab_sel_3"), types.InlineKeyboardButton("🐎 4", callback_data="cab_sel_4"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_caballos"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🐎 **Carrera Caballos**\nElige tu corcel ganador.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    elif juego == 'esfera':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🔮 Sí", callback_data="esfera_sel_si"), types.InlineKeyboardButton("🔮 No", callback_data="esfera_sel_no"))
        markup.add(types.InlineKeyboardButton("ℹ️ Ayuda", callback_data="ayuda_esfera"), types.InlineKeyboardButton("🔙 Volver", callback_data="volver_juegos"))
        bot.edit_message_text("🔮 **Esfera de la Suerte**\nConsulta tu destino.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'volver_juegos')
def callback_volver_juegos(call):
    mostrar_menu_juegos(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ayuda_'))
def mostrar_ayuda_juego(call):
    juego = call.data.replace('ayuda_', '')
    textos_ayuda = {
        "caracruz": "🪙 **Ayuda - Cara o Cruz**\nProbabilidad de victoria del 35%.",
        "dados": "🎲 **Ayuda - Dados**\nProbabilidad de victoria del 35%.",
        "slots": "🎰 **Ayuda - Tragamonedas**\nProbabilidad de victoria del 35%.",
        "ruleta": "🎡 **Ayuda - Ruleta**\nProbabilidad de victoria del 35%.",
        "blackjack": "🃏 **Ayuda - Blackjack Rápido**\nProbabilidad de victoria del 35%.",
        "crash": "🚀 **Ayuda - Crash Multiplicador**\nProbabilidad de victoria del 35%.",
        "baccarat": "🎴 **Ayuda - Baccarat**\nProbabilidad de victoria del 35%.",
        "cofre": "📦 **Ayuda - Cofre Oculto**\nProbabilidad de victoria del 35%.",
        "caballos": "🐎 **Ayuda - Carrera de Caballos**\nProbabilidad de victoria del 35%.",
        "esfera": "🔮 **Ayuda - Esfera de la Suerte**\nProbabilidad de victoria del 35%."
    }
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Volver al Juego", callback_data=f"juego_{juego}"))
    bot.edit_message_text(textos_ayuda.get(juego, "Sin información."), call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: '_sel_' in call.data)
def solicitar_apuesta_final_juego(call):
    user_id = call.from_user.id
    APUESTAS_TEMPORALES[user_id] = {"accion": call.data}

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("50 🪙", callback_data="bet_monto_50"),
        types.InlineKeyboardButton("100 🪙", callback_data="bet_monto_100"),
        types.InlineKeyboardButton("200 🪙", callback_data="bet_monto_200"),
        types.InlineKeyboardButton("500 🪙 (Máx)", callback_data="bet_monto_500"),
        types.InlineKeyboardButton("✏️ Personalizada", callback_data="bet_monto_custom")
    )
    markup.add(types.InlineKeyboardButton("🔙 Cancelar", callback_data="volver_juegos"))
    bot.edit_message_text("⚙️ **Selecciona tu cantidad a apostar**\n*(Límite estricto máximo de 500 fichas)*:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('bet_monto_') and call.data != 'bet_monto_custom')
def callback_monto_fijo_juego(call):
    user_id = call.from_user.id
    if user_id not in APUESTAS_TEMPORALES:
        bot.answer_callback_query(call.id, "❌ Sesión expirada. Vuelve a elegir el juego.", show_alert=True)
        return

    monto = int(call.data.replace('bet_monto_', ''))
    APUESTAS_TEMPORALES[user_id]["monto"] = monto
    datos = APUESTAS_TEMPORALES[user_id]
    accion_base = datos["accion"]
    
    juego_nombre = obtener_nombre_juego_desde_accion(accion_base)

    user_data = obtener_usuario(user_id)
    if user_data['saldo'] < monto:
        bot.answer_callback_query(call.id, f"❌ Saldo insuficiente. Necesitas {monto} fichas.", show_alert=True)
        return

    simular_ejecucion_juego(call.message, user_id, accion_base, monto, edit_msg=True, juego_key=juego_nombre)

@bot.callback_query_handler(func=lambda call: call.data == 'bet_monto_custom')
def callback_monto_custom_juego(call):
    user_id = call.from_user.id
    if user_id not in APUESTAS_TEMPORALES:
        bot.answer_callback_query(call.id, "❌ Sesión expirada.", show_alert=True)
        return
    msg = bot.send_message(call.message.chat.id, "✏️ Escribe una cantidad personalizada para apostar (Entre 1 y 500 fichas):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, recibir_apuesta_personalizada_juego)

def recibir_apuesta_personalizada_juego(message):
    user_id = message.from_user.id
    if message.text == '/cancelar' or user_id not in APUESTAS_TEMPORALES:
        bot.reply_to(message, "Cancelado.")
        if user_id in APUESTAS_TEMPORALES:
            del APUESTAS_TEMPORALES[user_id]
        return
    try:
        monto = int(message.text)
        if monto < 1 or monto > 500:
            msg_err = bot.reply_to(message, "❌ La apuesta debe estar entre 1 y **500 fichas**. Inténtalo de nuevo:")
            bot.register_next_step_handler(msg_err, recibir_apuesta_personalizada_juego)
            return

        user_data = obtener_usuario(user_id)
        if user_data['saldo'] < monto:
            msg_err = bot.reply_to(message, f"❌ No tienes suficientes fichas. Tu saldo es {user_data['saldo']}. Ingresa otra cantidad:")
            bot.register_next_step_handler(msg_err, recibir_apuesta_personalizada_juego)
            return

        APUESTAS_TEMPORALES[user_id]["monto"] = monto
        datos = APUESTAS_TEMPORALES[user_id]
        accion_base = datos["accion"]
        juego_nombre = obtener_nombre_juego_desde_accion(accion_base)

        simular_ejecucion_juego(message, user_id, accion_base, monto, edit_msg=False, juego_key=juego_nombre)

    except ValueError:
        msg_err = bot.reply_to(message, "❌ Número inválido. Escribe un número entero entre 1 y 500:")
        bot.register_next_step_handler(msg_err, recibir_apuesta_personalizada_juego)

def obtener_nombre_juego_desde_accion(accion):
    if accion.startswith('cc_sel_'): return 'caracruz'
    elif accion.startswith('dado_sel_'): return 'dados'
    elif accion == 'slot_sel_girar': return 'slots'
    elif accion.startswith('rul_sel_'): return 'ruleta'
    elif accion.startswith('bj_sel_'): return 'blackjack'
    elif accion.startswith('crash_sel_'): return 'crash'
    elif accion.startswith('bac_sel_'): return 'baccarat'
    elif accion.startswith('cofre_sel_'): return 'cofre'
    elif accion.startswith('cab_sel_'): return 'caballos'
    elif accion.startswith('esfera_sel_'): return 'esfera'
    return 'caracruz'

def markup_fin_continuo(juego_nombre):
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("🔄 Repetir Apuesta", callback_data=f"repetir_apuesta_{juego_nombre}"),
        types.InlineKeyboardButton("⚙️ Cambiar Monto", callback_data=f"juego_{juego_nombre}")
    )
    m.add(
        types.InlineKeyboardButton("🎮 Menú Juegos", callback_data="volver_juegos"),
        types.InlineKeyboardButton("🏠 Menú Principal", callback_data="volver_menu_principal_cb")
    )
    return m

@bot.callback_query_handler(func=lambda call: call.data.startswith('repetir_apuesta_'))
def callback_repetir_apuesta(call):
    user_id = call.from_user.id
    juego_nombre = call.data.replace('repetir_apuesta_', '')
    
    if user_id not in APUESTAS_TEMPORALES or "accion" not in APUESTAS_TEMPORALES[user_id] or "monto" not in APUESTAS_TEMPORALES[user_id]:
        bot.answer_callback_query(call.id, "⚠️ No hay apuesta previa registrada. Selecciona tu jugada nuevamente.", show_alert=True)
        mostrar_menu_juegos(call.message.chat.id, call.message.message_id)
        return

    datos_previos = APUESTAS_TEMPORALES[user_id]
    accion_base = datos_previos["accion"]
    monto = datos_previos["monto"]
    user_data = obtener_usuario(user_id)

    if user_data['saldo'] < monto:
        bot.answer_callback_query(call.id, f"❌ Saldo insuficiente. Necesitas {monto} fichas para repetir esta apuesta.", show_alert=True)
        return

    simular_ejecucion_juego(call.message, user_id, accion_base, monto, edit_msg=True, juego_key=juego_nombre)

def simular_ejecucion_juego(message_obj, user_id, accion_base, apuesta, edit_msg=False, juego_key='caracruz'):
    user_data = obtener_usuario(user_id)
    mult = user_data.get("multiplicador_ganancia", 1.0)

    chat_id = message_obj.chat.id if hasattr(message_obj, 'chat') else message_obj.message.chat.id
    msg_id = message_obj.message_id if hasattr(message_obj, 'message_id') else None

    # Control general de probabilidad de victoria ajustada a un 35% exacto
    gano_partida = random.random() < 0.35

    if accion_base.startswith('cc_sel_'):
        eleccion = accion_base.replace('cc_sel_', '')
        resultado = eleccion if gano_partida else ('cruz' if eleccion == 'cara' else 'cara')
        if gano_partida:
            premio = int(apuesta * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🪙 Cayó **{resultado.upper()}**.\n🎉 ¡Ganaste **+{premio} fichas**!\n 💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"🪙 Cayó **{resultado.upper()}**.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('dado_sel_'):
        eleccion = accion_base.replace('dado_sel_', '')
        dado_msg = bot.send_dice(chat_id, emoji='🎲')
        time.sleep(2)
        
        # Forzar resultado para cumplir el 35% de victoria del usuario
        if gano_partida:
            val = random.choice([2, 4, 6]) if eleccion == 'par' else random.choice([1, 3, 5])
        else:
            val = random.choice([1, 3, 5]) if eleccion == 'par' else random.choice([2, 4, 6])

        if gano_partida:
            premio = int(apuesta * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            bot.send_message(chat_id, f"🎲 Salió `{val}`.\n🎉 ¡Ganaste **+{premio} fichas**!\n💰 Saldo: **${user_data['saldo']}**", reply_markup=markup_fin_continuo(juego_key), parse_mode="Markdown")
            return
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            bot.send_message(chat_id, f"🎲 Salió `{val}`.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**", reply_markup=markup_fin_continuo(juego_key), parse_mode="Markdown")
            return

    elif accion_base == 'slot_sel_girar':
        simbolos = ["🍒", "🍋", "🔔", "⭐", "💎"]
        if gano_partida:
            r1 = r2 = r3 = random.choice(simbolos)
            premio = int((apuesta * 5) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🎰 | {r1} | {r2} | {r3} |\n🔥 ¡Premio Mayor! Ganaste **+{premio} fichas**!\n💰 Saldo: **${user_data['saldo']}**"
        else:
            r1, r2, r3 = random.sample(simbolos, 3)
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"🎰 | {r1} | {r2} | {r3} |\n❌ Sin premio. Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('rul_sel_'):
        eleccion = accion_base.replace('rul_sel_', '')
        resultado = eleccion if gano_partida else ('negro' if eleccion == 'rojo' else 'rojo')
        if gano_partida:
            premio = int((apuesta * 1.8) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🎡 Cayó **{resultado.upper()}**.\n🎉 ¡Ganaste **+{premio} fichas**!\n 💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"🎡 Cayó **{resultado.upper()}**.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('bj_sel_'):
        eleccion = accion_base.replace('bj_sel_', '')
        if eleccion == 'pedir':
            carta_extra = random.randint(1, 11)
            total = 16 + carta_extra
            if gano_partida and total <= 21:
                premio = int((apuesta * 1.5) * mult)
                user_data['saldo'] += premio
                actualizar_campo(user_id, 'saldo', user_data['saldo'])
                registrar_partida(user_id, gano=True)
                texto = f"🃏 Salió `{carta_extra}` (Total: {total}).\n🎉 ¡Ganaste **+{premio} fichas**!\n💰 Saldo: **${user_data['saldo']}**"
            else:
                user_data['saldo'] -= apuesta
                actualizar_campo(user_id, 'saldo', user_data['saldo'])
                registrar_partida(user_id, gano=False)
                texto = f"🃏 Salió `{carta_extra}` (Total: {total}). ¡Te pasaste!\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"
        else:
            if gano_partida:
                premio = int(apuesta * mult)
                user_data['saldo'] += premio
                actualizar_campo(user_id, 'saldo', user_data['saldo'])
                registrar_partida(user_id, gano=True)
                texto = f"🛑 Te plantaste. Ganaste **+{premio} fichas**!\n💰 Saldo: **${user_data['saldo']}**"
            else:
                user_data['saldo'] -= apuesta
                actualizar_campo(user_id, 'saldo', user_data['saldo'])
                registrar_partida(user_id, gano=False)
                texto = f"🛑 Te plantaste. La casa ganó.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('crash_sel_'):
        objetivo = float(accion_base.replace('crash_sel_', ''))
        explosion = objetivo + 0.5 if gano_partida else max(1.0, objetivo - 0.3)
        if gano_partida:
            premio = int((apuesta * objetivo) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🚀 Retiraste en `{objetivo}x`! (Explosión: {explosion}x).\n 🎉 ¡Ganaste **+{premio} fichas**!\n 💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"💥 ¡Crash en `{explosion}x`!\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('bac_sel_'):
        eleccion = accion_base.replace('bac_sel_', '')
        resultado = eleccion if gano_partida else ('banca' if eleccion == 'jugador' else 'jugador')
        if gano_partida:
            premio = int((apuesta * 1.9) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🎴 Ganó: **{resultado.upper()}**.\n🎉 ¡Ganaste **+{premio} fichas**!\n💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"🎴 Ganó: **{resultado.upper()}**.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('cofre_sel_'):
        eleccion = accion_base.replace('cofre_sel_', '')
        ganador = eleccion if gano_partida else str((int(eleccion) % 3) + 1)
        if gano_partida:
            premio = int((apuesta * 3) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"📦 ¡Era el cofre #{ganador}!\n🎉 ¡Tesoro encontrado! Ganaste **+{premio} fichas**.\n💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"📦 El cofre ganador era el #{ganador}.\n❌ Vacío. Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('cab_sel_'):
        eleccion = accion_base.replace('cab_sel_', '')
        ganador = eleccion if gano_partida else str((int(eleccion) % 4) + 1)
        if gano_partida:
            premio = int((apuesta * 4) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🐎 ¡Ganó el caballo #{ganador}!\n 🎉 ¡Ganaste **+{premio} fichas**!\n 💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"🐎 Ganó el caballo #{ganador}.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    elif accion_base.startswith('esfera_sel_'):
        eleccion = accion_base.replace('esfera_sel_', '')
        resultado = eleccion if gano_partida else ('no' if eleccion == 'si' else 'si')
        if gano_partida:
            premio = int((apuesta * 1.7) * mult)
            user_data['saldo'] += premio
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=True)
            texto = f"🔮 ¡Visión acertada!\n🎉 ¡Ganaste **+{premio} fichas**!\n💰 Saldo: **${user_data['saldo']}**"
        else:
            user_data['saldo'] -= apuesta
            actualizar_campo(user_id, 'saldo', user_data['saldo'])
            registrar_partida(user_id, gano=False)
            texto = f"🔮 Visión contraria.\n❌ Perdiste **-{apuesta} fichas**.\n💰 Saldo: **${user_data['saldo']}**"

    if edit_msg:
        try:
            bot.edit_message_text(texto, chat_id, msg_id, reply_markup=markup_fin_continuo(juego_key), parse_mode="Markdown")
            return
        except Exception:
            pass
    bot.send_message(chat_id, texto, reply_markup=markup_fin_continuo(juego_key), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'volver_menu_principal_cb')
def volver_menu_principal_cb(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    enviar_bienvenida_segun_rol(call.message)

# ================= PANEL DE ADMINISTRACIÓN =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def callback_admin(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Acceso denegado.")
        return

    data = call.data
    if data == "admin_pagos":
        db = cargar_datos()
        texto_pendientes = "📋 **Solicitudes Pendientes:**\n\n"
        markup = types.InlineKeyboardMarkup(row_width=2)
        hay_pendientes = False
        for uid, udata in db["usuarios"].items():
            if udata.get("pendiente_deposito", 0) > 0:
                hay_pendientes = True
                texto_pendientes += f"Depósito - User `{uid}`: {udata['pendiente_deposito']} fichas\n"
                markup.add(types.InlineKeyboardButton(f"✅ Aprobar Dep {uid}", callback_data=f"ap_dep_{uid}"))
            if udata.get("pendiente_retiro", 0) > 0:
                hay_pendientes = True
                texto_pendientes += f"Retiro - User `{uid}`: {udata['pendiente_retiro']} fichas\n"
                markup.add(types.InlineKeyboardButton(f"✅ Aprobar Ret {uid}", callback_data=f"ap_ret_{uid}"))
        if not hay_pendientes:
            texto_pendientes = "No hay solicitudes pendientes."
        bot.edit_message_text(texto_pendientes, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "admin_stats":
        db = cargar_datos()
        total_usuarios = len(db["usuarios"])
        fichas_totales = sum(u.get("saldo", 0) for u in db["usuarios"].values())
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"📊 **Estadísticas Globales**\n- Usuarios: `{total_usuarios}`\n- Fichas circulando: `${fichas_totales}`", parse_mode="Markdown")

    elif data == "admin_dar":
        msg = bot.send_message(call.message.chat.id, "Escribe el ID del usuario y la cantidad (Ej: `123456 500`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_dar_fichas_step)
    elif data == "admin_quitar":
        msg = bot.send_message(call.message.chat.id, "Escribe el ID del usuario y la cantidad a restar (Ej: `123456 500`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_quitar_fichas_step)
    elif data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "Escribe el mensaje para todos los usuarios:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_broadcast_step)
    elif data == "admin_ban":
        msg = bot.send_message(call.message.chat.id, "Escribe el ID del usuario a banear/desbanear:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_ban_step)
    elif data == "admin_cupon":
        msg = bot.send_message(call.message.chat.id, "Escribe el código y el valor (Ej: `BONO 1000`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_crear_cupon_step)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ap_'))
def callback_admin_pagos(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Acceso denegado.")
        return
    data = call.data
    if data.startswith("ap_dep_"):
        uid = data.split("_")[2]
        db = cargar_datos()
        if uid in db["usuarios"]:
            monto = db["usuarios"][uid]['pendiente_deposito']
            db["usuarios"][uid]['saldo'] += monto
            db["usuarios"][uid]['pendiente_deposito'] = 0
            guardar_datos(db)
            bot.answer_callback_query(call.id, f"Depósito acreditado.")
            bot.send_message(int(uid), f"🎉 ¡Tu depósito de **{monto} fichas** ha sido aprobado!", parse_mode="Markdown")
            bot.edit_message_text(f"✅ Depósito de {uid} aprobado.", call.message.chat.id, call.message.message_id)

    elif data.startswith("ap_ret_"):
        uid = data.split("_")[2]
        db = cargar_datos()
        if uid in db["usuarios"]:
            monto = db["usuarios"][uid]['pendiente_retiro']
            db["usuarios"][uid]['saldo'] -= monto
            db["usuarios"][uid]['retiro_hoy'] += monto
            db["usuarios"][uid]['pendiente_retiro'] = 0
            guardar_datos(db)
            bot.answer_callback_query(call.id, "Retiro procesado.")
            bot.send_message(int(uid), f"💸 Tu retiro de **{monto} fichas** ha sido procesado.", parse_mode="Markdown")
            bot.edit_message_text(f"✅ Retiro de {uid} aprobado.", call.message.chat.id, call.message.message_id)

# ================= PASOS Y FUNCIONES AUXILIARES =================
def procesar_deposito(message):
    if message.text == '/cancelar':
        bot.reply_to(message, "Cancelado.")
        return
    try:
        cantidad = int(message.text)
        if cantidad < 500:
            msg_err = bot.reply_to(message, "❌ Mínimo 500 fichas. Escribe una cantidad válida o /cancelar:")
            bot.register_next_step_handler(msg_err, procesar_deposito)
            return
        actualizar_campo(message.from_user.id, 'pendiente_deposito', cantidad)
        bot.reply_to(message, f"✅ Depósito de **{cantidad} fichas** registrado.", parse_mode="Markdown")
        bot.send_message(ADMIN_ID, f"🔔 Depósito pendiente de `{message.from_user.id}` por {cantidad}")
    except ValueError:
        msg_err = bot.reply_to(message, "❌ Número inválido. Escribe un valor numérico o /cancelar:")
        bot.register_next_step_handler(msg_err, procesar_deposito)

def procesar_retiro(message):
    if message.text == '/cancelar':
        bot.reply_to(message, "Cancelado.")
        return
    try:
        cantidad = int(message.text)
        user_data = obtener_usuario(message.from_user.id)
        if cantidad < 500 or cantidad > user_data['saldo'] or (user_data['retiro_hoy'] + cantidad) > 10000:
            msg_err = bot.reply_to(message, "❌ Error en los límites de retiro. Inténtalo de nuevo o /cancelar:")
            bot.register_next_step_handler(msg_err, procesar_retiro)
            return
        actualizar_campo(message.from_user.id, 'pendiente_retiro', cantidad)
        bot.reply_to(message, f"✅ Retiro de **{cantidad} fichas** solicitado.", parse_mode="Markdown")
        bot.send_message(ADMIN_ID, f"🔔 Retiro pendiente de `{message.from_user.id}` por {cantidad}")
    except ValueError:
        msg_err = bot.reply_to(message, "❌ Número inválido. Escribe un valor numérico o /cancelar:")
        bot.register_next_step_handler(msg_err, procesar_retiro)

def procesar_canje_cupon(message):
    codigo = message.text.strip().upper()
    db = cargar_datos()
    if "cupones" in db and codigo in db["cupones"] and db["cupones"][codigo]["usos"] > 0:
        db["cupones"][codigo]["usos"] -= 1
        valor = db["cupones"][codigo]["valor"]
        db["usuarios"][str(message.from_user.id)]["saldo"] += valor
        guardar_datos(db)
        bot.reply_to(message, f"🎉 ¡Cupón canjeado! Recibiste **{valor} fichas**.", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Cupón inválido o agotado.")

def admin_dar_fichas_step(message):
    try:
        partes = message.text.split()
        uid, monto = partes[0], int(partes[1])
        db = cargar_datos()
        if uid in db["usuarios"]:
            db["usuarios"][uid]["saldo"] += monto
            guardar_datos(db)
            bot.reply_to(message, f"✅ Se sumaron {monto} fichas a {uid}.")
            try:
                bot.send_message(int(uid), f"🎁 ¡Recibiste **{monto} fichas** de la administración!", parse_mode="Markdown")
            except Exception:
                pass
    except Exception:
        msg_err = bot.reply_to(message, "Error en el formato. Usa: `ID_USUARIO MONTO`. Reintenta:")
        bot.register_next_step_handler(msg_err, admin_dar_fichas_step)

def admin_quitar_fichas_step(message):
    try:
        partes = message.text.split()
        uid, monto = partes[0], int(partes[1])
        db = cargar_datos()
        if uid in db["usuarios"]:
            db["usuarios"][uid]["saldo"] = max(0, db["usuarios"][uid]["saldo"] - monto)
            guardar_datos(db)
            bot.reply_to(message, f"✅ Se descontaron {monto} fichas a {uid}.")
    except Exception:
        msg_err = bot.reply_to(message, "Error en el formato. Usa: `ID_USUARIO MONTO`. Reintenta:")
        bot.register_next_step_handler(msg_err, admin_quitar_fichas_step)

def admin_broadcast_step(message):
    db = cargar_datos()
    for uid in db["usuarios"]:
        try:
            bot.send_message(int(uid), f"📢 **Anuncio oficial:**\n\n{message.text}", parse_mode="Markdown")
        except Exception:
            pass
    bot.reply_to(message, "✅ Anuncio enviado.")

def admin_ban_step(message):
    uid = message.text.strip()
    db = cargar_datos()
    if uid in db["usuarios"]:
        db["usuarios"][uid]["banned"] = not db["usuarios"][uid].get("banned", False)
        estado = db["usuarios"][uid]["banned"]
        guardar_datos(db)
        bot.reply_to(message, f"✅ Estado de baneo actualizado para {uid} (Baneado: {estado}).")

def admin_crear_cupon_step(message):
    try:
        partes = message.text.split()
        codigo, valor = partes[0].upper(), int(partes[1])
        db = cargar_datos()
        if "cupones" not in db:
            db["cupones"] = {}
        db["cupones"][codigo] = {"valor": valor, "usos": 50}
        guardar_datos(db)
        bot.reply_to(message, f"✅ Cupón `{codigo}` creado por {valor} fichas.", parse_mode="Markdown")
    except Exception:
        msg_err = bot.reply_to(message, "Error en el formato. Usa: `CODIGO VALOR`. Reintenta:")
        bot.register_next_step_handler(msg_err, admin_crear_cupon_step)

# ================= MENÚS DE MEMBRESÍAS VIP =================
PLANES_MEMBRESIA = {
    "lite": {"nombre": "Lite 🟢", "costo": 100, "diario": 10, "horas_req": 2},
    "bronce": {"nombre": "Bronce 🥉", "costo": 300, "diario": 25, "horas_req": 5},
    "plata": {"nombre": "Plata 🥈", "costo": 600, "diario": 55, "horas_req": 10},
    "oro": {"nombre": "Oro 🥇", "costo": 1200, "diario": 120, "horas_req": 20},
    "diamante": {"nombre": "Diamante 💎", "costo": 2500, "diario": 270, "horas_req": 40}
}

def mostrar_menu_membresias(chat_id, message_id=None, es_nuevo=False, user_data=None):
    if not user_data:
        user_data = obtener_usuario(chat_id)

    activa = user_data.get("membresia_activa")
    horas_usuario = user_data.get("horas_actividad", 0.0)

    markup = types.InlineKeyboardMarkup(row_width=1)
    if not activa:
        for clave, info in PLANES_MEMBRESIA.items():
            markup.add(types.InlineKeyboardButton(f"💎 Comprar {info['nombre']} ({info['costo']} fichas)", callback_data=f"comprar_memb_{clave}"))
    else:
        info_actual = PLANES_MEMBRESIA.get(activa, {})
        markup.add(types.InlineKeyboardButton(f"🎁 Reclamar Pago Diario ({info_actual.get('diario', 0)} fichas)", callback_data="reclamar_memb"))
        markup.add(types.InlineKeyboardButton("❌ Cancelar / Cambiar Membresía", callback_data="cancelar_memb"))

    markup.add(types.InlineKeyboardButton("🔙 Menú Principal", callback_data="volver_menu_principal_cb"))

    texto = f"💎 **Centro de Membresías VIP**\n⏱️ Tus horas actuales: `{horas_usuario}h`\n\n"
    if activa:
        info = PLANES_MEMBRESIA[activa]
        texto += f"📌 **Activa:** {info['nombre']} (Pago diario: `{info['diario']} fichas`)\n"
    else:
        texto += "📋 **Planes Disponibles (15 días):**\n"
        for clave, info in PLANES_MEMBRESIA.items():
            texto += f"• **{info['nombre']}**: Costo `{info['costo']}` | Paga `{info['diario']}/día` | Req: `{info['horas_req']}h`\n"

    if es_nuevo:
        bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")
    else:
        try:
            bot.edit_message_text(texto, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('comprar_memb_') or call.data in ['reclamar_memb', 'cancelar_memb'])
def manejar_membresias_callback(call):
    user_id = call.from_user.id
    db = cargar_datos()
    user_data = db["usuarios"].get(str(user_id), obtener_usuario(user_id))

    if call.data.startswith('comprar_memb_'):
        if user_data.get("membresia_activa"):
            bot.answer_callback_query(call.id, "❌ Ya tienes una membresía activa.", show_alert=True)
            return

        clave = call.data.replace('comprar_memb_', '')
        plan = PLANES_MEMBRESIA.get(clave)
        if not plan:
            return

        if user_data['saldo'] < plan['costo']:
            bot.answer_callback_query(call.id, f"❌ Necesitas {plan['costo']} fichas.", show_alert=True)
            return

        user_data['saldo'] -= plan['costo']
        user_data['membresia_activa'] = clave
        user_data['membresia_vencimiento'] = time.time() + (15 * 86400)
        user_data['membresia_cobros'] = 0
        user_data['ultimo_cobro_membresia'] = 0
        guardar_datos(db)

        bot.answer_callback_query(call.id, f"🎉 ¡Membresía {plan['nombre']} adquirida!")
        mostrar_menu_membresias(call.message.chat.id, call.message.message_id, user_data=user_data)

    elif call.data == 'reclamar_memb':
        activa = user_data.get("membresia_activa")
        if not activa:
            bot.answer_callback_query(call.id, "❌ No tienes membresía activa.", show_alert=True)
            return

        plan = PLANES_MEMBRESIA[activa]

        if user_data.get("horas_actividad", 0.0) < plan["horas_req"]:
            bot.answer_callback_query(call.id, f"❌ Requieres al menos {plan['horas_req']}h de actividad acumulada.", show_alert=True)
            return

        tiempo_actual = time.time()
        ultimo_cobro = user_data.get("ultimo_cobro_membresia", 0)
        if tiempo_actual - ultimo_cobro < 86400:
            tiempo_restante = int(86400 - (tiempo_actual - ultimo_cobro))
            h = tiempo_restante // 3600
            m = (tiempo_restante % 3600) // 60
            bot.answer_callback_query(call.id, f"⏳ Ya reclamaste tu pago de hoy. Vuelve en {h}h {m}m.", show_alert=True)
            return

        if user_data.get("membresia_cobros", 0) >= 15:
            bot.answer_callback_query(call.id, "🎉 ¡Membresía completada (15 días cumplidos)!", show_alert=True)
            user_data["membresia_activa"] = None
            guardar_datos(db)
            mostrar_menu_membresias(call.message.chat.id, call.message.message_id, user_data=user_data)
            return

        user_data['saldo'] += plan['diario']
        user_data['membresia_cobros'] += 1
        user_data['ultimo_cobro_membresia'] = tiempo_actual
        guardar_datos(db)

        bot.answer_callback_query(call.id, f"🎉 +{plan['diario']} fichas cobradas exitosamente.")
        mostrar_menu_membresias(call.message.chat.id, call.message.message_id, user_data=user_data)

    elif call.data == 'cancelar_memb':
        user_data['membresia_activa'] = None
        user_data['membresia_cobros'] = 0
        user_data['ultimo_cobro_membresia'] = 0
        guardar_datos(db)
        bot.answer_callback_query(call.id, "⚠️ Membresía cancelada.")
        mostrar_menu_membresias(call.message.chat.id, call.message.message_id, user_data=user_data)

# ================= TIENDA DE TÍTULOS Y MISIONES =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('comprar_titulo_') or call.data in ['reclamar_m1', 'reclamar_m2', 'mision_ya_reclamada', 'mision_en_progreso'])
def manejar_tienda_y_misiones_reestructurado(call):
    user_id = call.from_user.id
    db = cargar_datos()
    str_uid = str(user_id)
    user_data = db["usuarios"].get(str_uid, obtener_usuario(user_id))

    if call.data == 'comprar_titulo_1':
        costo = 1000
        if user_data['saldo'] < costo:
            bot.answer_callback_query(call.id, f"❌ Requieres {costo} fichas.", show_alert=True)
            return
        user_data['saldo'] -= costo
        user_data['multiplicador_ganancia'] = 1.01
        guardar_datos(db)
        bot.answer_callback_query(call.id, "🎉 ¡Título Apostador comprado y fichas descontadas!")
        bot.edit_message_text(f"🛍️ ¡Compra exitosa!\nAdquiriste **♠️ Apostador** (+1% ganancia pasiva).\n💰 Saldo actual: **${user_data['saldo']}** fichas", call.message.chat.id, call.message.message_id)

    elif call.data == 'comprar_titulo_2':
        costo = 5000
        if user_data['saldo'] < costo:
            bot.answer_callback_query(call.id, f"❌ Requieres {costo} fichas.", show_alert=True)
            return
        user_data['saldo'] -= costo
        user_data['multiplicador_ganancia'] = 1.03
        guardar_datos(db)
        bot.answer_callback_query(call.id, "🎉 ¡Título High Roller comprado y fichas descontadas!")
        bot.edit_message_text(f"🛍️ ¡Compra exitosa!\nAdquiriste **🔥 High Roller** (+3% ganancia pasiva).\n💰 Saldo actual: **${user_data['saldo']}** fichas", call.message.chat.id, call.message.message_id)

    elif call.data == 'comprar_titulo_3':
        costo = 15000
        if user_data['saldo'] < costo:
            bot.answer_callback_query(call.id, f"❌ Requieres {costo} fichas.", show_alert=True)
            return
        user_data['saldo'] -= costo
        user_data['multiplicador_ganancia'] = 1.05
        guardar_datos(db)
        bot.answer_callback_query(call.id, "🎉 ¡Título Rey del Casino comprado y fichas descontadas!")
        bot.edit_message_text(f"🛍️ ¡Compra exitosa!\nAdquiriste **👑 Rey del Casino** (+5% ganancia pasiva).\n💰 Saldo actual: **${user_data['saldo']}** fichas", call.message.chat.id, call.message.message_id)

    elif call.data == 'reclamar_m1':
        juegos = user_data.get("mision_juegos", 0)
        if juegos < 5:
            bot.answer_callback_query(call.id, "❌ Aún no cumples el requisito de 5 partidas.", show_alert=True)
            return
        if user_data.get("recompensa_mision_1", False):
            bot.answer_callback_query(call.id, "❌ Esta misión ya fue reclamada hoy. Vuelve mañana.", show_alert=True)
            return

        user_data["saldo"] += 150
        user_data["recompensa_mision_1"] = True
        guardar_datos(db)
        bot.answer_callback_query(call.id, "🎉 ¡+150 fichas acreditadas!")
        bot.edit_message_text(f"🎁 **Misión 1 Completada**\n¡Recibiste **+150 fichas** acreditadas a tu saldo!\n💰 Nuevo saldo: **${user_data['saldo']}** fichas", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data == 'reclamar_m2':
        vics = user_data.get("mision_victorias", 0)
        if vics < 3:
            bot.answer_callback_query(call.id, "❌ Aún no cumples el requisito de 3 victorias.", show_alert=True)
            return
        if user_data.get("recompensa_mision_2", False):
            bot.answer_callback_query(call.id, "❌ Esta misión ya fue reclamada hoy. Vuelve mañana.", show_alert=True)
            return

        user_data["saldo"] += 250
        user_data["recompensa_mision_2"] = True
        guardar_datos(db)
        bot.answer_callback_query(call.id, "🎉 ¡+250 fichas acreditadas!")
        bot.edit_message_text(f"🎁 **Misión 2 Completada**\n¡Recibiste **+250 fichas** acreditadas a tu saldo!\n💰 Nuevo saldo: **${user_data['saldo']}** fichas", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data == 'mision_ya_reclamada':
        bot.answer_callback_query(call.id, "⏳ Ya reclamaste esta misión hoy.", show_alert=True)

    elif call.data == 'mision_en_progreso':
        bot.answer_callback_query(call.id, "⏳ Completa el objetivo del juego.", show_alert=True)

# ================= DUELOS =================
@bot.callback_query_handler(func=lambda call: call.data in ['crear_duelo', 'ver_duelos'] or call.data.startswith('unirse_duelo_'))
def manejar_duelos(call):
    user_id = call.from_user.id
    user_data = obtener_usuario(user_id)
    db = cargar_datos()

    if call.data == 'crear_duelo':
        if user_data['saldo'] < 100:
            bot.answer_callback_query(call.id, "❌ Necesitas 100 fichas.", show_alert=True)
            return
        user_data['saldo'] -= 100
        guardar_datos(db)

        duelo_id = str(random.randint(1000, 9999))
        db["duelos"][duelo_id] = {"creador": user_id, "username": call.from_user.username or "Anónimo", "monto": 100}
        guardar_datos(db)

        bot.answer_callback_query(call.id, "✅ Duelo creado con éxito!")
        bot.edit_message_text(f"⚔️ **Duelo creado (ID: {duelo_id})**\nEsperando oponente...", call.message.chat.id, call.message.message_id)

    elif call.data == 'ver_duelos':
        duelos = db["duelos"]
        if not duelos:
            bot.answer_callback_query(call.id, "No hay duelos activos.", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for did, dinfo in duelos.items():
            if int(dinfo["creador"]) != user_id:
                markup.add(types.InlineKeyboardButton(f"⚔️ Retar al usuario @{dinfo['username']} ({dinfo['monto']} fichas)", callback_data=f"unirse_duelo_{did}"))

        markup.add(types.InlineKeyboardButton("🔙 Volver", callback_data="volver_menu_principal_cb"))
        bot.edit_message_text("📋 **Duelos Disponibles:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith('unirse_duelo_'):
        did = call.data.replace('unirse_duelo_', '')
        db = cargar_datos()
        if did not in db["duelos"]:
            bot.answer_callback_query(call.id, "❌ Duelo no disponible.", show_alert=True)
            return

        if user_data['saldo'] < 100:
            bot.answer_callback_query(call.id, "❌ Necesitas 100 fichas.", show_alert=True)
            return

        dinfo = db["duelos"].pop(did)
        creador_id = int(dinfo["creador"])
        db["usuarios"][str(user_id)]["saldo"] -= 100

        dado1 = random.randint(1, 6)
        dado2 = random.randint(1, 6)
        texto_res = f"⚔️ **Resultado del Duelo PvP**\n\nRetador (@{dinfo['username']}): `{dado1}`\nOponente: `{dado2}`\n\n"

        if dado1 > dado2:
            db["usuarios"][str(creador_id)]["saldo"] += 200
            registrar_partida(creador_id, gano=True)
            registrar_partida(user_id, gano=False)
            texto_res += f"🎉 ¡Ganó @{dinfo['username']} (+200 fichas)!"
            try: bot.send_message(creador_id, f"🎉 ¡Ganaste el duelo PvP (+200 fichas)!", parse_mode="Markdown")
            except Exception: pass
        elif dado2 > dado1:
            db["usuarios"][str(user_id)]["saldo"] += 200
            registrar_partida(user_id, gano=True)
            registrar_partida(creador_id, gano=False)
            texto_res += f"🎉 ¡Ganaste el duelo PvP (+200 fichas)!"
        else:
            db["usuarios"][str(creador_id)]["saldo"] += 100
            db["usuarios"][str(user_id)]["saldo"] += 100
            texto_res += "🤝 ¡Empate! Se devuelven las fichas."
            try: bot.send_message(creador_id, "🤝 Duelo empatado. Fichas devueltas.", parse_mode="Markdown")
            except Exception: pass

        guardar_datos(db)
        markup_fin = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🏠 Menú Principal", callback_data="volver_menu_principal_cb"))
        bot.edit_message_text(texto_res, call.message.chat.id, call.message.message_id, reply_markup=markup_fin, parse_mode="Markdown")

if __name__ == '__main__':
    print("Bot casino optimizado, con juego dinámico continuo y corriendo en Termux...")
    bot.infinity_polling()
