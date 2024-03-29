#!/usr/bin/python3
# coding:utf-8

import configparser
import logging
import os
import os.path
import uuid
from functools import wraps

import magic
import requests
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Read config
config = configparser.ConfigParser()
config.read('config.ini')
# Set logging
logging_level = config['DEBUG']['LOGGING_LEVEL']
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.getLevelName(logging_level))
logger = logging.getLogger(__name__)


# handler functions
def send_typing_action(function):
    @wraps(function)
    async def command_function(update, context, *args, **kwargs):
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.constants.ChatAction.TYPING)
        await function(update, context, *args, **kwargs)

    return command_function


@send_typing_action
async def get_help(update, context):
    allowed_format = config['HOST']['ALLOWED_FILE_FORMAT']
    max_file_size = config['HOST']['MAX_FILE_SIZE']
    await context.bot.send_message(chat_id=update.message.chat_id,
                                   text=f'Send me photo or image file.\n'
                                        f'Available format: {allowed_format}\n'
                                        f'Max file size: {max_file_size}MB')


async def uptime(update, context):
    uptime_command = os.popen("uptime")
    uptime_output = uptime_command.read()
    await context.bot.send_message(chat_id=update.message.chat_id, text=uptime_output)


async def storage_status(update, context):
    storage_status_command = os.popen("df -lh")
    storage_status_output = storage_status_command.read()
    await context.bot.send_message(chat_id=update.message.chat_id, text=storage_status_output)


async def cache_status(update, context):
    cache_path = os.getcwd() + '/cache'
    cache_files_count = str(
        len([name for name in os.listdir(cache_path) if os.path.isfile(os.path.join(cache_path, name))]))
    cache_files_size = str(cache_files_size_count(cache_path))
    cache_status_message = f'Current cache status:\n' \
                           f'Cache files count: {cache_files_count}\n' \
                           f'Cache files size: {cache_files_size}'
    await context.bot.send_message(chat_id=update.message.chat_id, text=cache_status_message)


def cache_files_size_count(cache_path):
    size = 0
    for dirpath, dirnames, filenames in os.walk(cache_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            size += os.path.getsize(fp)
    return size


async def cache_clean(update, context):
    cache_path = os.getcwd() + '/cache'
    cache_files_list = os.listdir(cache_path)

    for cache in cache_files_list:
        if cache.endswith(".jpg") or cache.endswith(".cache"):
            os.remove(os.path.join(cache_path, cache))

    await context.bot.send_message(chat_id=update.message.chat_id, text='All upload cache are cleared.')


@send_typing_action
async def unknown_msg(update, context):
    await context.bot.send_message(chat_id=update.message.chat_id, text='Please send me photo or image file only!')


@send_typing_action
async def image(update, context):
    image_id = update.message.photo[-1].file_id
    image_name = '%s.jpg' % str(uuid.uuid4())
    image_path = os.getcwd() + '/cache/' + image_name
    image_raw = await context.bot.get_file(image_id)
    await image_raw.download_to_drive(image_path)
    reply_message = await update.message.reply_text('Downloading image from Telegram server...')
    await reply_message.edit_text(image_upload(image_path))


@send_typing_action
async def image_file(update, context):
    allowed_image_file_format = config['HOST']['ALLOWED_FILE_MINE']
    image_file_id = update.message.document.file_id
    image_file_name = '%s.cache' % str(uuid.uuid4())
    image_file_path = os.getcwd() + '/cache/' + image_file_name
    image_file_raw = await context.bot.get_file(image_file_id)
    await image_file_raw.download_to_drive(image_file_path)
    image_file_mime = magic.from_file(image_file_path, mime=True)

    if image_file_mime in allowed_image_file_format:
        reply_message = await update.message.reply_text('Downloading image file from Telegram server...')
        await reply_message.edit_text(image_upload(image_file_path))
    else:
        allowed_format = config['HOST']['ALLOWED_FILE_FORMAT']
        await update.message.reply_text(f'Please send me {allowed_format} format image file only!')
        os.remove(image_file_path)


def image_upload(image_file_name):
    return_data = do_image_upload(request_format(image_file_name))

    if return_data.status_code == 200:
        return_data = return_data.json()
        url_viewer = return_data['image']['url_viewer']
        url = return_data['image']['url']
        uploaded_info = f'Upload succeeded!\n' \
                        f'Web viewer: {url_viewer}\n' \
                        f'Origin size: {url}'

        return uploaded_info
    else:
        logger.error(return_data.content)
        os.remove(image_file_name)

        return 'Image Host error! Please try again later.'


def do_image_upload(images):
    image_host = config['HOST']['IMAGE_HOST']
    image_host_api_key = config['HOST']['IMAGE_HOST_API_KEY']
    image_host_return_format = config['HOST']['IMAGE_HOST_RETURN_FORMAT']
    request_url = f'https://{image_host}/api/1/upload/?format={image_host_return_format}'
    upload_response = requests.post(
        request_url,
        headers={
            'User-Agent': 'Chevereto Telegram Bot',
            'X-API-Key': image_host_api_key
        },
        files=images,
    )
    logger.info(upload_response)

    return upload_response


# Build the request format
def request_format(image_name):
    image_upload_request = []
    image_type = magic.from_file(image_name, mime=True)
    image_upload_request.append(('source', (image_name, open(image_name, 'rb'), image_type)))
    logger.info(image_type + str(image_upload_request))

    return image_upload_request


def main():
    # Check cache folder exists
    if not os.path.exists('cache'):
        os.makedirs('cache')

    app = Application.builder().token(config['BOT']['ACCESS_TOKEN']).build()
    admin_user_id = int(config['BOT']['ADMIN_USER_ID'])
    # handlers
    # /help
    app.add_handler(CommandHandler("help", get_help))
    # /uptime
    app.add_handler(CommandHandler("uptime", uptime))
    # /storage_status
    app.add_handler(
        CommandHandler("storage_status", storage_status, filters=filters.User(admin_user_id)))
    # /cache_status
    app.add_handler(
        CommandHandler("cache_status", cache_status, filters=filters.User(admin_user_id)))
    # /cache_clean
    app.add_handler(
        CommandHandler("cache_clean", cache_clean, filters=filters.User(admin_user_id)))
    # Process image
    image_handler = MessageHandler(filters.PHOTO, image)
    app.add_handler(image_handler)
    # Process image file
    image_file_handler = MessageHandler(filters.Document.Category('image/'), image_file)
    app.add_handler(image_file_handler)
    # Unknown message
    unknown_msg_handler = MessageHandler(filters.ChatType.PRIVATE, unknown_msg)
    app.add_handler(unknown_msg_handler)
    # Run bot
    if config['BOT']['MODE'] == 'PULLING':
        app.run_polling()
    elif config['BOT']['MODE'] == 'WEBHOOK':
        webhook_url = 'https://' + config['BOT']['WEBHOOK_URL']

        if config['BOT']['WEBHOOK_SSL'] == 'True':
            app.run_webhook(
                listen=config['BOT']['WEBHOOK_LISTEN'],
                port=config['BOT']['WEBHOOK_PORT'],
                key=config['BOT']['WEBHOOK_SSL_KEY'],
                cert=config['BOT']['WEBHOOK_SSL_CERT'],
                webhook_url=webhook_url
            )
        else:
            app.run_webhook(
                listen=config['BOT']['WEBHOOK_LISTEN'],
                port=config['BOT']['WEBHOOK_PORT'],
                webhook_url=webhook_url
            )

    else:
        exit()


if __name__ == '__main__':
    main()
