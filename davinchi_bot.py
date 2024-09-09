from telegram import Update, ReplyKeyboardMarkup, Bot, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler
from telegram.ext import CallbackContext, filters, ContextTypes
import configparser
import logging
import requests
from pymongo import MongoClient
from gridfs import GridFS
from io import BytesIO
import hashlib
import datetime, pytz, time

def read_config(filename='bot_config.txt', section='telegrambot'):
    # Create a parser
    parser = configparser.ConfigParser()
    # Read config file
    parser.read(filename, encoding='utf-8')

    # Get section, default to mysql
    data = {}
    if parser.has_section(section):
        items = parser.items(section)
        for item in items:
            data[item[0]] = item[1]
    else:
        raise Exception(f'{section} not found in the {filename} file')

    return data


data = read_config()
TOKEN = data['token']
bot_name = data['bot_name']
admin_name = data['admin_name']
service_URL = data['service_url']
mongo_URL = data['mongo_url']


# Define states for the conversation
NAME, AGE, SEX, INTERESTED_IN, ABOUT_ME, UPLOADING_PHOTO = range(6)
USERNAME, PASSWORD, SUPERUSER_ACTION = range(3)
CHOOSING_UPDATE, UPDATING = range(2)
SHOWING_PARTNER, RESPONDING_TO_PARTNER = range(2)

bot = Bot(TOKEN)

# MongoDB setup
client = MongoClient(mongo_URL)
db = client['tinder_bot']
fs = GridFS(db)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



def main_keyboard():
    keyboard_layout = [['Update Profile', 'Show Profile', 'Find someone']]
    return ReplyKeyboardMarkup(keyboard_layout, one_time_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = requests.get(f"{service_URL}/users/{update.effective_user.id}")
    if response.json():
        await update.message.reply_text("Нету надобности заново прожимать старт, ты и так зареган", reply_markup=main_keyboard())
        return ConversationHandler.END
    logger.info("User %s started the conversation.", update.effective_user.id)
    await update.message.reply_text("Привет! Я твой Данильчик бот. Давай познакомимся! 🚀\n\nКак тебя зовут?")
    return NAME 

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    logger.info("User %s provided name: %s", update.effective_user.id, update.message.text)
    await update.message.reply_text("Сколько тебе лет?")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    try:
        if int(context.user_data['age']) < 18:
            await update.message.reply_text("Давай притворимся, что я не увидел какой у тебя возраст, напиши нормальный")
            return AGE   
    except:
        await update.message.reply_text("Возраст неправильно указан")
        return AGE 
    logger.info("User %s provided age: %s", update.effective_user.id, update.message.text)
    await update.message.reply_text("Какой у тебя пол?", reply_markup=sex_keyboard())
    return SEX

async def get_sex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sex'] = update.message.text
    logger.info("User %s provided sex: %s", update.effective_user.id, update.message.text)
    await update.message.reply_text("Кого ты ищешь?", reply_markup=interested_in_keyboard())
    return INTERESTED_IN

async def get_interested_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['interested_in'] = update.message.text
    logger.info("User %s is interested in: %s", update.effective_user.id, update.message.text)
    await update.message.reply_text("Расскажи немного о себе.")
    return ABOUT_ME

async def get_about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['about_me'] = update.message.text
    logger.info("User %s provided about_me: %s", update.effective_user.id, update.message.text)
    await update.message.reply_text("Пожалуйста, загрузите свои фото (необходимо 3). ОБЯЗАТЕЛЬНО ОТПРАВЛЯЙ ПО ОДНОМУ ФОТО ЗА РАЗ.")
    return UPLOADING_PHOTO

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_mongo = db.user_data.find_one({"telegram_id": user_id})
    
    if not user_mongo:
        db.user_data.insert_one({"telegram_id": user_id, 'photos': []})
        user_mongo = db.user_data.find_one({"telegram_id": user_id})

    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    # Store the photo in GridFS
    photo_file_io = BytesIO(photo_bytes)  # Wrap photo_bytes in BytesIO
    photo_id = fs.put(photo_file_io, filename=f"{user_id}_photo{len(user_mongo['photos'])}")

    db.user_data.update_one(
        {"telegram_id": user_id},
        {"$push": {"photos": photo_id}},
        upsert=True
    )
    print(len(user_mongo['photos']))
    if len(user_mongo['photos']) < 2:
        await update.message.reply_text("Пожалуйста, загрузите еще одно фото.")
        return UPLOADING_PHOTO
    else:
        if context.user_data.get('update_profile'):
            await update.message.reply_text("Ваши фото успешно обновлены.", reply_markup=main_keyboard())
            return ConversationHandler.END
        else:
            user_data = {
                "telegram_id": user_id,
                "name": context.user_data['name'],
                "age": context.user_data['age'],
                "sex": context.user_data['sex'],
                "interested_in": context.user_data['interested_in'],
                "about_me": context.user_data['about_me']
            }
            try:

                rec_array = [doc['telegram_id'] for doc in db.user_data.find({}, {'telegram_id': 1})]
                rec_array.remove(user_id)

                db.user_data.update_one(
                    {"telegram_id": user_id},
                    {"$set": {"partners": rec_array}}
                    )


                response = requests.post(f"{service_URL}/users", json=user_data)
                response.raise_for_status()  # Check if the request was successful
                await update.message.reply_text(f"Спасибо за заполнение профиля! Вот что я записал:\n\n" +
                                                f"Имя: {context.user_data['name']}\n" +
                                                f"Возраст: {context.user_data['age']}\n" +
                                                f"Пол: {context.user_data['sex']}\n" +
                                                f"Интересуется: {context.user_data['interested_in']}\n" +
                                                f"О себе: {context.user_data['about_me']}\n\n" +
                                                "Профиль успешно добавлен в базу данных!", reply_markup=main_keyboard())
                
            except requests.exceptions.RequestException as e:
                logger.error("Failed to add user to database: %s", e)
                await update.message.reply_text("Произошла ошибка при добавлении профиля в базу данных. Пожалуйста, попробуйте позже.", reply_markup=main_keyboard())
    
            return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.", reply_markup=main_keyboard())
    return ConversationHandler.END

# Helper functions to create keyboards
def sex_keyboard():
    keyboard = [['Man', 'Woman']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def interested_in_keyboard():
    keyboard = [['Man', 'Woman', 'Both']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

async def update_profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['Name', 'Age'], ['Sex', 'Interested In'], ['About Me', 'Photos']]
    await context.bot.send_message(update.effective_chat.id, "Что бы ты хотел изменить в своем профиле?", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return CHOOSING_UPDATE

async def update_profile_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    context.user_data['update_choice'] = text
    if text == 'Photos':
        context.user_data['update_profile'] = True  # Indicate that we are updating the profile
        await update.message.reply_text("Пожалуйста, загрузите свои фото (необходимо 3). ОБЯЗАТЕЛЬНО ОТПРАВЛЯЙ ПО ОДНОМУ ФОТО ЗА РАЗ.")
        
        # Get the photo ObjectIds from the document
        photo_ids = db.user_data.find_one({"telegram_id": user_id}).get('photos', [])

        # Delete each photo from GridFS
        for photo_id in photo_ids:
            logger.info("User %s updates his photos.", update.effective_user.id)
            fs.delete(photo_id)

        db.user_data.update_one(
        {"telegram_id": user_id},
        {"$set": {"photos": []}}
        )
        return UPLOADING_PHOTO
    else:
        await update.message.reply_text(f"Ты выбрал обновить: {text}. Какое новое значение?")
        return UPDATING

async def update_profile_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = context.user_data['update_choice']
    new_value = update.message.text

    user_id = update.effective_user.id
    update_data = {}

    if choice == 'Name':
        update_data['name'] = new_value
    elif choice == 'Age':
        try:
            update_data['age'] = new_value
            if int(update_data['age']) < 18:
                raise ValueError
        except ValueError as e:
            logger.error("Failed to update user profile: %s", e)
            await update.message.reply_text("Нам тут не до шуток, пиши нормально", reply_markup=main_keyboard())    
            return ConversationHandler.END
    elif choice == 'Sex':
        if new_value in ['Man', 'Woman']:
            update_data['sex'] = new_value
        else:
            await update.message.reply_text("Ты непонятно что написал, переделывай", reply_markup=main_keyboard())
            return ConversationHandler.END 
    elif choice == 'Interested In':
        update_data['interested_in'] = new_value
        if new_value in ['Man', 'Woman', 'Both']:
            update_data['sex'] = new_value
        else:
            await update.message.reply_text("Ты непонятно что написал, переделывай", reply_markup=main_keyboard())
            return ConversationHandler.END 
    elif choice == 'About Me':
        update_data['about_me'] = new_value

    try:
        response = requests.put(f"{service_URL}/users/{user_id}", json=update_data)
        status_code = response.status_code
        print("__"*5+str(status_code)+"__"*5)
        await update.message.reply_text("Профиль успешно обновлен!", reply_markup=main_keyboard())
    except requests.exceptions.RequestException as e:
        logger.error("Failed to update user profile: %s", e)
        await update.message.reply_text("Произошла ошибка при обновлении профиля. Пожалуйста, попробуйте позже.", reply_markup=main_keyboard())

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Обновление профиля отменено.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def show_profile_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_mongo = db.user_data.find_one({"telegram_id": user_id})

    if not user_mongo:
        await update.message.reply_text("Сначала зарегистрируйтесь с помощью команды /start.", reply_markup=main_keyboard())
        return ConversationHandler.END
    try:
        response = requests.get(f"{service_URL}/users/{user_id}")
        response.raise_for_status()
        user_data = response.json()
        user_data = user_data[0] 
        profile_info = f"Имя: {user_data.get('Name')}\n" \
                       f"Возраст: {user_data.get('Age')}\n" \
                       f"Пол: {user_data.get('Sex')}\n" \
                       f"Интересуется: {user_data.get('Interested_in')}\n" \
                       f"О себе: {user_data.get('About_me')}"
        # Send the profile information along with each photo
        if 'photos' in user_mongo:
            photos = []
            for photo_id in user_mongo['photos']:
                photo_bytes = fs.get(photo_id).read()
                photos.append(InputMediaPhoto(photo_bytes))
            await update.message.reply_text("Вот информация о вашем профиле:", reply_markup=main_keyboard())
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=photos, 
                                            caption=profile_info)
            
        else:
            await update.message.reply_text("Вот информация о вашем профиле:\n\n" + profile_info, reply_markup=main_keyboard())
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch user profile: %s", e)
        await update.message.reply_text("Произошла ошибка при получении информации о профиле. Пожалуйста, попробуйте позже.", reply_markup=main_keyboard())

async def find_partner_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_mongo = db.user_data.find_one({"telegram_id": user_id})
    response = requests.get(f"{service_URL}/users/{user_id}")
    is_banned = response.json()[0]['Is_banned']

    if is_banned:
        await update.message.reply_text("Вы забанены.", reply_markup=main_keyboard())
        return ConversationHandler.END
    
    if not user_mongo or not user_mongo.get('partners'):
        await update.message.reply_text("Нет доступных партнеров для отображения.", reply_markup=main_keyboard())
        return ConversationHandler.END

    # Fetch the next partner from the list
    partner_id = user_mongo['partners'][0]
    context.user_data['partner_id'] = partner_id

    # Get partner data
    partner_mongo = db.user_data.find_one({"telegram_id": partner_id})
    if not partner_mongo:
        # If the partner doesn't exist in the database, remove them from the list and try again
        db.user_data.update_one(
            {"telegram_id": user_id},
            {"$pull": {"partners": partner_id}}
        )
        await find_partner_command(update, context)
        return

    try:
        response = requests.get(f"{service_URL}/users/{partner_id}")
        response.raise_for_status()
        partner_data = response.json()
        partner_data = partner_data[0]
        profile_info = f"Имя: {partner_data.get('Name')}\n" \
                       f"Возраст: {partner_data.get('Age')}\n" \
                       f"Пол: {partner_data.get('Sex')}\n" \
                       f"Интересуется: {partner_data.get('Interested_in')}\n" \
                       f"О себе: {partner_data.get('About_me')}"
        print(profile_info)
        # Send the profile information along with each photo
        if 'photos' in partner_mongo:
            photos = []
            for photo_id in partner_mongo['photos']:
                photo_bytes = fs.get(photo_id).read()
                photos.append(InputMediaPhoto(photo_bytes))
            await update.message.reply_text("Вот информация о возможном партнере:", reply_markup=main_keyboard())
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=photos, caption=profile_info)
        
        else:
            await update.message.reply_text("Вот информация о возможном партнере:\n\n" + profile_info, reply_markup=main_keyboard())
        
        # Ask the user if they like the partner
        await update.message.reply_text("Вам нравится этот партнер? (❤️/💩)", reply_markup=ReplyKeyboardMarkup([['❤️', '💩', '❌', '🚫']], one_time_keyboard=True))
        return RESPONDING_TO_PARTNER

    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch partner profile: %s", e)
        await update.message.reply_text("Произошла ошибка при получении информации о партнере. Пожалуйста, попробуйте позже.", reply_markup=main_keyboard())
        return ConversationHandler.END


def get_match_profile_data(user_id, username):
    response = requests.get(f"{service_URL}/users/{user_id}")
    response.raise_for_status()
    
    user_mongo = db.user_data.find_one({"telegram_id": user_id})

    user_data = response.json()
    user_data = user_data[0]

    if username:

        profile_info = f'<a href="tg://user?id={user_id}">{user_data.get("Name")}</a>\n' \
                    f'Username: @{username}\n' \
                    f'Возраст: {user_data.get("Age")}\n' \
                    f'О себе: {user_data.get("About_me")}'
    
    else:
        profile_info = f'<a href="tg://user?id={user_id}">{user_data.get("Name")}</a>\n' \
                    f'Возраст: {user_data.get("Age")}\n' \
                    f'О себе: {user_data.get("About_me")}'
    
    # Send the profile information along with each photo
    if 'photos' in user_mongo:
        photos = []
        for photo_id in user_mongo['photos']:
            photo_bytes = fs.get(photo_id).read()
            photos.append(InputMediaPhoto(photo_bytes))
    print(profile_info)
    
    return profile_info, photos
                                           
async def handle_partner_response(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_response = update.message.text
    partner_id = context.user_data['partner_id']

    if user_response == '❌':
        await update.message.reply_text("Всего доброго", reply_markup=main_keyboard())
        return ConversationHandler.END

    # Remove the shown partner from the list
    db.user_data.update_one(
        {"telegram_id": user_id},
        {"$pull": {"partners": partner_id}}
    )

    interaction_type = "like" if user_response == '❤️' else "dislike"
    interaction_data = {
        "user_id": user_id,
        "interacted_user_id": partner_id,
        "interaction_type": interaction_type
    }

    try:
        # Send POST request to create the interaction
        response = requests.post(f"{service_URL}/interactions", json=interaction_data)
        response.raise_for_status()  # Check if the request was successful

        flag = 1
        if user_response == '❤️':
            response = requests.get(f"{service_URL}/match/{user_id}/{partner_id}")
            if response.json():

                flag = 0

                user = await context.bot.get_chat(user_id)
                profile_info, photos = get_match_profile_data(user_id, user.username)
                await context.bot.send_message(partner_id, "У вас Match!!!")
                await context.bot.send_media_group(chat_id=partner_id, media=photos, caption=profile_info, parse_mode="html")

                user = await context.bot.get_chat(partner_id)
                profile_info, photos = get_match_profile_data(partner_id, user.username)
                await context.bot.send_message(user_id, "У вас Match!!!")
                await context.bot.send_media_group(chat_id=user_id, media=photos, caption=profile_info, parse_mode="html")
        
        if user_response == '🚫':
            data_list = {"reporter_id": user_id, "reported_user_id": partner_id}
            response = requests.post(f"{service_URL}/report_user", json=data_list)
            logger.info("User %s reported user %s, status %s.", user_id, partner_id, response.status_code)
        
        if flag:
            await update.message.reply_text("Ваше взаимодействие сохранено.", reply_markup=main_keyboard())

    except requests.exceptions.RequestException as e:
        logger.error("Failed to create interaction: %s", e)
        await update.message.reply_text("Произошла ошибка при сохранении взаимодействия. Пожалуйста, попробуйте позже.", reply_markup=main_keyboard())
        return ConversationHandler.END

    # Check if there are more partners to show
    user_mongo = db.user_data.find_one({"telegram_id": user_id})
    if not user_mongo.get('partners'):
        await update.message.reply_text("Нет доступных партнеров для отображения.", reply_markup=main_keyboard())
        return ConversationHandler.END
    else:
        return await find_partner_command(update, context)



async def superuser_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter your username:")
    return USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    await context.bot.delete_message(chat_id=update.effective_user.id, message_id=update.message.message_id)
    await update.message.reply_text("Please enter your password:")
    return PASSWORD

def hash_password_sha256(password):
    # Prepend the salt to the password and hash it
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    # Return the salt and hashed password
    return hashed_password

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = hash_password_sha256(update.message.text)
    username = context.user_data['username']
    user_id = update.effective_user.id

    try:
        await context.bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
        response = requests.get(f"{service_URL}/superuser_login/{username}/{password}/{user_id}")
        if response.status_code == 200:
            await update.message.reply_text("Вход в систему успешный. Получение наиболее зарегистрированных пользователей...")
            return await show_most_reported_user(update, context)
        else:
            await update.message.reply_text("Вход в систему не удался. Пожалуйста, попробуйте еще раз.")
            return ConversationHandler.END

    except requests.exceptions.RequestException as e:
        logger.error("Failed to login as superuser: %s", e)
        await update.message.reply_text("При входе в систему произошла ошибка. Пожалуйста, повторите попытку позже.")
        return ConversationHandler.END

async def show_most_reported_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{service_URL}/most_reported_user")
        if response.status_code == 200:
            user_data = response.json()[0]
            user_id = user_data['reported_user_id']
            user = await context.bot.get_chat(user_id)
            profile_info, photos = get_match_profile_data(user_id, user.username)
            await context.bot.send_media_group(update.effective_user.id, media=photos, caption=profile_info, parse_mode="html")
            await context.bot.send_message(update.effective_user.id, 'Выберите что с ним сделать', reply_markup=superuser_keyboard())
            context.user_data['reported_user_id'] = user_data['reported_user_id']
            return SUPERUSER_ACTION
        else:
            await update.message.reply_text("Пользователи не обнаружены", reply_markup=main_keyboard())
            return ConversationHandler.END

    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch most reported user: %s", e)
        await update.message.reply_text("An error occurred while fetching the most reported user. Please try again later.")
        return ConversationHandler.END

async def handle_superuser_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = update.message.text
    user_id = context.user_data['reported_user_id']

    if action == 'Ban':
        status = 'banned'
    elif action == 'Skip':
        status = 'reviewed'
    else:
        await update.message.reply_text("Logging out...", reply_markup=main_keyboard())
        return ConversationHandler.END

    try:
        response = requests.put(f"{service_URL}/change_user_report_status/{user_id}", json={'status': status})
        if response.status_code == 200:
            await update.message.reply_text("Статус репорта пользователя успешно обновлен.")
            return await show_most_reported_user(update, context)
        else:
            await update.message.reply_text("Не удалось обновить статус репорта пользователя.")
            return ConversationHandler.END

    except requests.exceptions.RequestException as e:
        logger.error("Failed to update user report status: %s", e)
        await update.message.reply_text("Произошла ошибка при обновлении статуса отчета пользователя. Пожалуйста, повторите попытку позже.")
        return ConversationHandler.END

def superuser_keyboard():
    keyboard = [['Ban', 'Skip', 'Exit']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)


async def delete_interactions(update: Update, context: CallbackContext):
    response = requests.delete(f'{service_URL}/interactions_by_time')
    if response.status_code == 200:
        logger.info('Interactions data deleted succesfully')
    else:
        logger.info('No Interactions data found for delete')

async def update_recs(update: Update, context: CallbackContext):

    users = [doc['telegram_id'] for doc in db.user_data.find({}, {'telegram_id': 1})]
    for user_id in users:
        response = requests.get(f'{service_URL}/seek_for_partner/{user_id}') 
        db.user_data.update_one(
        {"telegram_id": user_id},
        {"$set": {"partners": response.json()}}
        )

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Операция отменена.", reply_markup=main_keyboard())
    return ConversationHandler.END


# Define conversation handlers
conv_handler_start = ConversationHandler(
    entry_points=[CommandHandler('start', start_command)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        SEX: [MessageHandler(filters.Regex(r'^Man|Woman$') & ~filters.COMMAND, get_sex)],
        INTERESTED_IN: [MessageHandler(filters.Regex(r'^Man|Woman|Both$') & ~filters.COMMAND, get_interested_in)],
        ABOUT_ME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_about_me)],
        UPLOADING_PHOTO: [MessageHandler(filters.PHOTO, handle_photo)]
    },
    fallbacks=[CommandHandler('start', start_command)],
)

conv_handler_superuser_login = ConversationHandler(
    entry_points=[CommandHandler('superuserlogin', superuser_login_command)],
    states={
        USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
        PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        SUPERUSER_ACTION: [MessageHandler(filters.Regex('^Ban|Skip|Exit$') & ~filters.COMMAND, handle_superuser_action)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

conv_handler_update_profile = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r'^Update Profile$'), update_profile_command)],
    states={
        CHOOSING_UPDATE: [MessageHandler(filters.Regex(r'^(Name|Age|Sex|Interested In|About Me|Photos)$'), update_profile_choice)],
        UPDATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_profile_value)],
        UPLOADING_PHOTO: [MessageHandler(filters.PHOTO, handle_photo)]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

partner_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(r'^Find someone$'), find_partner_command)],
    states={
        SHOWING_PARTNER: [MessageHandler(filters.Regex(r'^❤️|💩|❌|🚫$'), handle_partner_response)],
        RESPONDING_TO_PARTNER: [MessageHandler(filters.Regex(r'^❤️|💩|❌|🚫$'), handle_partner_response)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)
def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add the handler to the application
    application.add_handler(conv_handler_start)
    application.add_handler(conv_handler_superuser_login)
    application.add_handler(conv_handler_update_profile)
    application.add_handler(partner_conv_handler)

    application.add_handler(MessageHandler(filters.Regex(r'^Show Profile$'), show_profile_command))

    # application.job_queue.run_repeating(delete_interactions, interval=3600)
    # application.job_queue.run_repeating(update_recs, interval=86400)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
