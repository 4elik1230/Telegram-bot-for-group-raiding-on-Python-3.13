import telebot
from telebot import types
import time
import os
import json

TOKEN = 'your_token'
bot = telebot.TeleBot(TOKEN)
admin_1 = 'your_user_id'
admins = [admin_1]

CONFIG_DIR = 'configs'
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

virtual_mutes = {}
group_rules = "Правила еще не установлены"
forward = False
current_group_id = None 
group_id = -123456789

def is_admin(message):
    try:
        user_status = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return user_status in ['administrator', 'creator']
    except:
        return False

def get_all_groups():
    groups = []
    for filename in os.listdir(CONFIG_DIR):
        if filename.endswith('.json') and os.path.getsize(os.path.join(CONFIG_DIR, filename)) > 0:
            try:
                with open(os.path.join(CONFIG_DIR, filename), 'r', encoding='utf-8') as f:
                    groups.append(json.load(f))
            except: continue
    return groups

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id in admins:
        markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup_reply.add(types.KeyboardButton("➕ Добавить группу"))
        
        groups = get_all_groups()
        markup_inline = types.InlineKeyboardMarkup()
        
        if not groups:
            text = "Привет, хозяин! Добавленных групп пока нет."
        else:
            text = "Привет! Выбери группу для управления:"
            for g in groups:
                markup_inline.add(types.InlineKeyboardButton(text=g['name'], callback_data=f"select_{g['group_id']}"))
        
        bot.send_message(message.chat.id, text, reply_markup=markup_inline)
        bot.send_message(message.chat.id, "Используй кнопки ниже:", reply_markup=markup_reply)
    else:
        bot.reply_to(message, "Привет! \n я помощник для чатов \n Напиши /help чтобы узнать мои возможности")

@bot.message_handler(commands=['help'])
def send_help(message):
    if message.from_user.id in admins:
        help_text = "Команды админа:\n/deleteallusers - удалить всех\n/forwardon - вкл пересылку\n/forwardoff - выкл пересылку\n/getlink - ссылка"
        bot.send_message(message.chat.id, help_text)
    else:
        bot.send_message(message.chat.id, "Команды: /mute, /ban, /rules, /help")

@bot.message_handler(commands=['setrules'])
def set_rules(message):
    global group_rules
    if is_admin(message):
        new_rules = message.text.replace('/setrules', '').strip()
        if new_rules:
            group_rules = new_rules
            bot.reply_to(message, "✅ Правила чата обновленные!")
        else:
            bot.reply_to(message, "Пожалуйста, напишите текст правил после команды. Например: `/setrules уважайте друг друга!`")
    else:
        bot.reply_to(message, "❌ У вас нету прав для изменения правил.")

@bot.message_handler(commands=['rules'])
def get_rules(message):
    bot.reply_to(message, f"📋 **Правила группы:**\n\n{group_rules}", parse_mode="Markdown")

@bot.message_handler(commands=["mute"])
def mute(message):
    if message.chat.type == 'private':
        return

    if not message.reply_to_message:
        bot.reply_to(message, "Ответьте на пользователя котрого хотите замутить.")
        return

    if not is_admin(message):
        bot.reply_to(message, "❌ У вас нету прав администратора.")
        return

    try:
        args = message.text.split()
        hours = int(args[1]) if len(args) > 1 else 1
    except ValueError:
        bot.reply_to(message, "Ошибка. Например: `/mute 5`", parse_mode="Markdown")
        return

    user = message.reply_to_message.from_user
    until_timestamp = int(time.time()) + hours * 3600

    try:
        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            until_date=until_timestamp,
            permissions=types.ChatPermissions(can_send_messages=False)
        )
        bot.send_message(message.chat.id, f"Пользователь {user.first_name} замутен на {hours} ч.")
    
    except telebot.apihelper.ApiTelegramException as e:
        if "method is available only for supergroups" in str(e):
            virtual_mutes[user.id] = until_timestamp
            bot.send_message(message.chat.id, f"Пользователь {user.first_name} замутен на {hours} ч.")
        else:
            bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_admin(message):
        bot.reply_to(message, "❌ У вас нету прав администратора.")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "Ответьте на пользователя котрого хотите забанить")
        return

    try:
        bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message, f"🔨 Пользователь {message.reply_to_message.from_user.first_name} удален из группы.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new(message):
    for new_user in message.new_chat_members:
        if new_user.id == bot.get_me().id:
            continue
            
        welcome_msg = (
            f"Добро пожаловать в нашу группу, {new_user.first_name}! 👋\n\n"
            f"Пожалуйста ознакомьтесь правилами:\n{group_rules}"
        )
        bot.send_message(message.chat.id, welcome_msg)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить группу" and m.from_user.id in admins)
def add_group_start(message):
    msg = bot.send_message(message.chat.id, "Введите название группы:")
    bot.register_next_step_handler(msg, add_group_id)

def add_group_id(message):
    name = message.text
    msg = bot.send_message(message.chat.id, "Введите ID группы (с -100):")
    bot.register_next_step_handler(msg, add_group_users, name)

def add_group_users(message, name):
    try:
        g_id = int(message.text)
        msg = bot.send_message(message.chat.id, "Введите ID пользователей через запятую (или 0 если нет):")
        bot.register_next_step_handler(msg, save_group, name, g_id)
    except:
        bot.send_message(message.chat.id, "Ошибка в ID! Начни заново /start")

def save_group(message, name, g_id):
    try:
        raw_text = message.text
        
        clean_text = raw_text.replace(',', ' ').replace(';', ' ')
        
        u_ids = []
        for word in clean_text.split():
            if word.strip().replace('-', '').isdigit(): 
                u_ids.append(int(word.strip()))
        
        u_ids = list(set(u_ids))
        
        filename = f"{name.replace(' ', '_').lower()}.json"
        path = os.path.join(CONFIG_DIR, filename)
        
        data = {
            "name": name,
            "group_id": int(g_id),
            "blacklist": u_ids
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        bot.send_message(
            message.chat.id, 
            f"✅ Группа **{name}** сохранена!\n"
            f"📊 Найдено и сохранено ID: **{len(u_ids)}**\n"
            f"🎯 ID группы: `{g_id}`",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при обработке: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def handle_select(call):
    global current_group_id
    current_group_id = int(call.data.replace('select_', ''))
    bot.answer_callback_query(call.id, "Группа выбрана!")
    bot.send_message(call.message.chat.id, f"✅ Теперь управляем группой {current_group_id}")

@bot.message_handler(commands=['deleteallusers'])
def delete_all_users_logic(message):
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id
    
    if not target_id:
        bot.send_message(message.chat.id, "❌ Группа не выбрана! Нажми /start.")
        return

    users_to_ban = []
    group_name = "Неизвестная группа"
    
    for filename in os.listdir(CONFIG_DIR):
        if filename.endswith('.json'):
            path = os.path.join(CONFIG_DIR, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if int(data.get('group_id')) == int(target_id):
                    users_to_ban = data.get('blacklist', [])
                    group_name = data.get('name', 'Группа')
                    break
            except: continue

    if not users_to_ban:
        bot.send_message(message.chat.id, "⚠️ В списке этой группы нет пользователей для удаления.")
        return

    bot.send_message(message.chat.id, f"🚀 Начинаю бан {len(users_to_ban)} чел. в группе **{group_name}**...")
    
    success = 0
    errors = 0

    for u_id in users_to_ban:
        try:
            user_to_kick = int(u_id)
            
            bot.ban_chat_member(target_id, user_to_kick)
            
            success += 1
            time.sleep(0.2) 
            
        except Exception as e:
            errors += 1
            print(f"Ошибка бана {u_id}: {e}")

    bot.send_message(
        message.chat.id, 
        f"✅ Процесс завершен!\n"
        f"Успешно забанено: **{success}**\n"
        f"Не удалось (ошибки): **{errors}**\n\n"
        f"💡 Если много ошибок, проверь, есть ли у бота права админа в группе!"
    )

@bot.message_handler(commands=['spammsg'])
def spam_start(message):
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id
    
    if not target_id:
        bot.send_message(message.chat.id, "❌ Группа не выбрана! Нажми /start и выбери цель.")
        return

    msg = bot.send_message(message.chat.id, "🔢 **Шаг 1:** Введите количество сообщений для спама:")
    bot.register_next_step_handler(msg, spam_get_count)

def spam_get_count(message):
    try:
        count = int(message.text)
        if count <= 0:
            bot.send_message(message.chat.id, "Количество должно быть больше 0. Попробуй еще раз: /spammsg")
            return
        
        msg = bot.send_message(message.chat.id, "📝 **Шаг 2:** Теперь пришли сообщение (текст, фото или стикер), которое нужно спамить:")
        bot.register_next_step_handler(msg, spam_execute, count)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Ошибка! Нужно ввести целое число. Попробуй еще раз: /spammsg")

def spam_execute(message, count):
    target_id = current_group_id if current_group_id else group_id
    bot.send_message(message.chat.id, f"🚀 Запускаю рассылку {count} сообщений...")
    
    sent_count = 0
    while sent_count < count:
        try:
            bot.copy_message(target_id, message.chat.id, message.message_id)
            sent_count += 1
    
            time.sleep(1.2) 
            
            if sent_count % 10 == 0:
                bot.send_message(message.chat.id, f"📈 Прогресс: {sent_count}/{count} отправлено.")

        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = e.result_json['parameters']['retry_after']
                bot.send_message(message.chat.id, f"⏳ Telegram ограничил отправку. Жду {retry_after} сек. и продолжаю автоматически...")
                time.sleep(retry_after + 1)
                continue
            else:
                bot.send_message(message.chat.id, f"❌ Критическая ошибка: {e}")
                break
            
    bot.send_message(message.chat.id, f"✅ Спам завершен! Отправлено сообщений: {sent_count}")

@bot.message_handler(commands=["getlink"])
def get_link_cmd(message):
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id

    if not target_id:
        bot.send_message(message.chat.id, "❌ Группа не выбрана. Нажми /start")
        return

    try:
        link = bot.export_chat_invite_link(target_id)
        bot.send_message(message.chat.id, f"🔗 Ссылка на выбранную группу:\n{link}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Не удалось получить ссылку.\nОшибка: {e}\n\n(Убедись, что бот — админ в группе с правом приглашения пользователей)")

@bot.message_handler(commands=['forwardon'])
def forward_on(message):
    global forward
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id
    
    if not target_id:
        bot.send_message(message.chat.id, "❌ Группа не выбрана! Нажми /start и выбери группу, из которой нужно пересылать сообщения.")
        return

    forward = True
    
    groups = get_all_groups()
    group_name = next((g['name'] for g in groups if int(g['group_id']) == target_id), "выбранной группы")

    bot.send_message(message.chat.id, f"📡 **Пересылка ВКЛЮЧЕНА**\nТеперь сообщения из группы «{group_name}» будут дублироваться вам в личку.", parse_mode="Markdown")

@bot.message_handler(commands=['forwardoff'])
def forward_off(message):
    global forward
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    forward = False
    bot.send_message(message.chat.id, "🚫 **Пересылка ВЫКЛЮЧЕНА**", parse_mode="Markdown")

@bot.message_handler(commands=['rename'])
def rename_start(message):
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id
    
    if target_id is None or target_id == 0:
        bot.send_message(message.chat.id, "❌ **Группа не выбрана!**\n\nСначала нажми /start и выбери группу в списке, а уже потом пиши /rename.", parse_mode="Markdown")
        return 

    msg = bot.send_message(message.chat.id, "📝 Введите новое название для выбранной группы:")
    bot.register_next_step_handler(msg, rename_execute)

def rename_execute(message):
    target_id = current_group_id if current_group_id else group_id
    new_title = message.text

    if not new_title or new_title.startswith('/'):
        bot.send_message(message.chat.id, "❌ Отменено. Название не может быть пустым или командой.")
        return

    try:
        bot.set_chat_title(target_id, new_title)
        
        for filename in os.listdir(CONFIG_DIR):
            if filename.endswith('.json'):
                path = os.path.join(CONFIG_DIR, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if int(data.get('group_id')) == int(target_id):
                        data['name'] = new_title
                        with open(path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)
                        break
                except: continue

        bot.send_message(message.chat.id, f"✅ Успешно! Новое имя группы: **{new_title}**", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка API: {e}")

@bot.message_handler(commands=['setavatar'])
def set_avatar_start(message):
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id
    
    if target_id is None or target_id == 0:
        bot.send_message(message.chat.id, "❌ **Группа не выбрана!**\n\nСначала выбери группу через /start, а потом используй /setavatar.", parse_mode="Markdown")
        return

    msg = bot.send_message(message.chat.id, "📸 Отправьте **фотографию**, которую хотите поставить на аватарку группы:")
    bot.register_next_step_handler(msg, set_avatar_execute)

def set_avatar_execute(message):
    target_id = current_group_id if current_group_id else group_id

    if not message.photo:
        bot.send_message(message.chat.id, "❌ Это не фото! Попробуй еще раз /setavatar и отправь именно картинку.")
        return

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_photo = "temp_avatar.jpg"
        with open(temp_photo, 'wb') as new_file:
            new_file.write(downloaded_file)

        with open(temp_photo, 'rb') as photo:
            bot.set_chat_photo(target_id, photo)

        os.remove(temp_photo)

        bot.send_message(message.chat.id, "✅ **Аватарка группы успешно обновлена!**", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Не удалось сменить фото.\nОшибка: {e}\n\n(Убедись, что бот админ и может менять данные группы)")

@bot.message_handler(commands=['deleteconfig'])
def delete_config_cmd(message):
    global current_group_id
    if message.from_user.id not in admins or message.chat.type != "private":
        return

    target_id = current_group_id if current_group_id else group_id
    
    if target_id is None or target_id == 0:
        bot.send_message(message.chat.id, "❌ **Группа не выбрана!**\n\nСначала выбери группу через /start, которую хочешь удалить.", parse_mode="Markdown")
        return

    config_deleted = False
    for filename in os.listdir(CONFIG_DIR):
        if filename.endswith('.json'):
            path = os.path.join(CONFIG_DIR, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if int(data.get('group_id')) == int(target_id):
                    os.remove(path)
                    config_deleted = True
                    deleted_name = data.get('name', filename)
                    break
            except: continue

    if config_deleted:
        current_group_id = None
        bot.send_message(message.chat.id, f"🗑 **Конфиг группы «{deleted_name}» успешно удален!**\nСписок в /start обновлен.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Файл конфигурации для этой группы не найден.")

@bot.message_handler(func=lambda message: True, content_types=['text','photo','document','video','audio','sticker','animation','voice'])
def global_combined_handler(message):
    global forward, current_group_id
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id in virtual_mutes:
        if time.time() < virtual_mutes[user_id]:
            try:
                bot.delete_message(chat_id, message.message_id)
                return
            except: pass
        else:
            del virtual_mutes[user_id]

    if message.chat.type != "private":
        for filename in os.listdir(CONFIG_DIR):
            if filename.endswith('.json'):
                path = os.path.join(CONFIG_DIR, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if int(data.get('group_id', 0)) == chat_id:
                        if user_id not in data.get('blacklist', []) and user_id not in admins:
                            data.setdefault('blacklist', []).append(user_id)
                            with open(path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=4, ensure_ascii=False)
                except: continue

    if forward and chat_id == (current_group_id if current_group_id else group_id):
        for a in admins:
            try: bot.forward_message(a, chat_id, message.message_id)
            except: pass

if __name__ == "__main__":
    print("Бот успешно запущен!")
    bot.infinity_polling()