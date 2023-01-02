#!/usr/bin/python3
# coding:utf-8

import configparser
import json
import logging
import magic
import os
import os.path
import requests
import shutil
import sys
import telegram
import uuid
from functools import wraps
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from threading import Thread

#錯誤logging
logging.basicConfig(format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level = logging.INFO)
logger = logging.getLogger(__name__)

#加載config
config = configparser.ConfigParser()
config.read('config.ini')

#handler functions
def send_typing_action(function):
    @wraps(function)
    async def command_function(update, context, *args, **kwargs):
        await context.bot.send_chat_action(chat_id = update.message.chat_id, action = telegram.constants.ChatAction.TYPING)
        function(update, context, *args, **kwargs)
    return command_function

@send_typing_action
async def help(update, context):
    await context.bot.send_message(chat_id = update.message.chat_id, text = 'Send me some pictures or image file. Available format: .jpg, .png, bmp, .gif, 20MB max file size.')

async def uptime(update, context):
    uptime_command = os.popen("uptime")
    uptime_output = uptime_command.read()
    await context.bot.send_message(chat_id = update.message.chat_id, text = uptime_output)

async def storage_status(update, context):
    storage_status_command = os.popen("df -lh")
    storage_status_output = storage_status_command.read()
    await context.bot.send_message(chat_id = update.message.chat_id, text = storage_status_output)

async def cache_status(update, context):
    cache_path = os.getcwd()+'/cache'
    cache_files_count = str(len([name for name in os.listdir(cache_path) if os.path.isfile(os.path.join(cache_path, name))]))
    cache_files_size = str(cache_files_size_count(cache_path))
    cache_status_message = 'Current cache status:\nCache files count: ' + cache_files_count + '\nCache files size: ' + cache_files_size
    await context.bot.send_message(chat_id = update.message.chat_id, text = cache_status_message)

def cache_files_size_count(cache_path):
    size = 0
    for dirpath, dirnames, filenames in os.walk(cache_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            size += os.path.getsize(fp)
    return size

async def cache_clean(update, context):
    cache_path = os.getcwd()+'/cache'
    cache_files_list = os.listdir(cache_path)
    for cache in cache_files_list:
        if cache.endswith(".jpg"):
            os.remove(os.path.join(cache_path, cache))
        elif cache.endswith(".cache"):
            os.remove(os.path.join(cache_path, cache))
    await context.bot.send_message(chat_id = update.message.chat_id, text = 'All upload cache are cleared')

def restart_action():
    updater.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)

async def restart(update, context):
    await context.bot.send_message(chat_id = update.message.chat_id, text = 'Bot is restarting...')
    Thread(target = restart_action).start()

@send_typing_action
async def unknow_msg(update, context):
    await context.bot.send_message(chat_id = update.message.chat_id, text = 'Please send me pictures or image file only!')

@send_typing_action
async def image(update, context):
    image_id = update.message.photo[-1].file_id
    image_name = '%s.jpg' % str(uuid.uuid4())
    image = context.bot.getFile(image_id)
    image.download(image_name)
    update.message.reply_text('Downloading image from Telegram...')
    return_data = image_upload(request_format(image_name))
    if return_data['status_code'] == 200:
        shutil.move(image_name, 'cache/'+image_name)
        uploaded_info = 'Upload succeeded!\nHere are your links to this image:\nWeb viewer: ' + return_data['image']['url_viewer'] +'\nDirect Link: ' + return_data['image']['url']
        await update.message.reply_text(uploaded_info)
    else:
        print(return_data)
        await update.message.reply_text('Image Host error! Please try again later.')
        os.remove(image_name)

@send_typing_action
async def image_file(update, context):
    allowed_image_file_format = 'image/jpeg image/png image/bmp image/gif'
    image_file_id = update.message.document.file_id
    image_file_name = '%s.cache' % str(uuid.uuid4())
    image_file = context.bot.getFile(image_file_id)
    image_file.download(image_file_name)
    image_file_mime = magic.from_file(image_file_name, mime=True)
    if image_file_mime in allowed_image_file_format:
        update.message.reply_text('Downloading image file from Telegram...')
        return_data = image_upload(request_format(image_file_name))
        if return_data['status_code'] == 200:
            shutil.move(image_file_name, 'cache/'+image_file_name)
            uploaded_info = 'Upload succeeded!\nHere are your links to this image:\nWeb viewer: ' + return_data['image']['url_viewer'] +'\nOrigin size: ' + return_data['image']['url']
            await update.message.reply_text(uploaded_info)
        else:
            print(return_data)
            await update.message.reply_text('Image Host error! Please try again later.')
            os.remove(image_file_name)
    else:
        await update.message.reply_text('Please send me .JPG .PNG .BMP .GIF format file only!')
        os.remove(image_file_name)

def image_upload(images):
    image_host = config['HOST']['IMAGE_HOST']
    image_host_api_key = config['HOST']['IMAGE_HOST_API_KEY']
    image_host_return_format = config['HOST']['IMAGE_HOST_RETURN_FORMAT']
    request_url = 'https://' + image_host + '/api/1/upload/?key=' + image_host_api_key + '&format=' + image_host_return_format
    upload_response = requests.post(request_url, files = images)
    print(upload_response)
    return upload_response.json()

#構造upload請求
def request_format(image_name):
    image_upload_request = []
    image_type = magic.from_file(image_name, mime=True)
    image_upload_request.append(('source' , (image_name , open(image_name , 'rb') , image_type)))
    print(image_type)
    print(image_upload_request)
    return image_upload_request

def main():    
    bot = Application.builder().token(config['BOT']['ACCESS_TOKEN']).build()
    #handlers
    #/help指令處理
    bot.add_handler(CommandHandler("help", help))
    #/uptime指令處理
    bot.add_handler(CommandHandler("uptime", uptime))
    #/storage_status指令處理
    bot.add_handler(CommandHandler("storage_status", storage_status, filters=filters.User(user_id = config['BOT']['ADMIN_USER_ID'])))
    #/cache_status指令處理
    bot.add_handler(CommandHandler("cache_status", cache_status, filters=filters.User(user_id = config['BOT']['ADMIN_USER_ID'])))
    #/cache_clean指令處理
    bot.add_handler(CommandHandler("cache_clean", cache_clean, filters=filters.User(user_id = config['BOT']['ADMIN_USER_ID'])))
    #/restart指令處理
    bot.add_handler(CommandHandler("restart", restart, filters=filters.User(user_id = config['BOT']['ADMIN_USER_ID'])))
    #處理用戶發送的圖片
    image_handler = MessageHandler(filters.PHOTO, image)
    bot.add_handler(image_handler)
    #處理用戶發送的圖片文件
    image_file_handler = MessageHandler(filters.Document.Category('image/'), image_file)
    bot.add_handler(image_file_handler)
    #處理用戶私聊發送的未知訊息
    unknow_msg_handler = MessageHandler(filters.ChatType.PRIVATE, unknow_msg)
    bot.add_handler(unknow_msg_handler)
    #檢查緩存目錄是否存在
    if not os.path.exists('cache'):
        os.makedirs('cache')
    #啓動進程
    if config['BOT']['MODE'] == 'PULLING':
        bot.run_polling()
    elif config['BOT']['MODE'] == 'WEBHOOK':
        bot_webhook_url = 'https://' + config['BOT']['WEBHOOK_URL'] + ':' + config['BOT']['WEBHOOK_PORT'] + '/' + config['BOT']['ACCESS_TOKEN']
        bot.run_webhook(listen = "0.0.0.0",
                              port = int(config['BOT']['WEBHOOK_PORT']),
                              key = config['BOT']['WEBHOOK_KEY'],
                              cert = config['BOT']['WEBHOOK_CERT'],
                              url_path = config['BOT']['ACCESS_TOKEN'],
                              webhook_url = bot_webhook_url)
    else:
        exit()

if __name__ == '__main__':
    main()
