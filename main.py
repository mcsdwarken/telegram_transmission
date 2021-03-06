#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os, sys
from daemonize import Daemonize

import logging
import subprocess
import time

import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# Config file in the following format (one value per line):
# TOKEN
# TRANSMISSION_USER
# TRANSMISSION_PASSWORD
# AUTHORIZED_USERS (comma separated list)
# DEFAULT_DOWNLOAD_PATH
# DEFAULT_DOWNLOAD_FOLDER
SETTINGS_FILENAME = '/home/osmc/main.config'

telegram_bot = None 

with open(SETTINGS_FILENAME) as f:
  lineList = f.read().splitlines()
TOKEN, TRANSMISSION_USER, TRANSMISSION_PASSWORD, users, DEFAULT_DOWNLOAD_PATH, DEFAULT_DOWNLOAD_FOLDER = lineList
AUTHORIZED_USERS = list(map(int, users.split(',')))

TRANSMISSION_REMOTE_BASE = "transmission-remote -n '%s:%s' " % (TRANSMISSION_USER, TRANSMISSION_PASSWORD)

def execute_command(cmd, returns=True):
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = result.communicate()
    if returns:
        return "%s: %s%s%s" % (str(result.returncode), output, "" if not output else "\r\n", err) 

def cmd_add_torrent(magnet=None, location=DEFAULT_DOWNLOAD_FOLDER):
    cmd = "%s --add '%s'" % (TRANSMISSION_REMOTE_BASE, magnet)
    if location != DEFAULT_DOWNLOAD_FOLDER:
        download_dir = DEFAULT_DOWNLOAD_PATH + location
        cmd = "%s --download-dir %s" % (cmd, download_dir)
    return execute_command(cmd)

def cmd_manage_torrent(command, torrents):
    cmd = "%s -t %s %s" % (TRANSMISSION_REMOTE_BASE, torrents, command)
    return execute_command(cmd)

def cmd_torrent(command):
    cmd = "%s %s" % (TRANSMISSION_REMOTE_BASE, command)
    return execute_command(cmd)    

def cmd_ipsec(arg):
    if(arg not in ["start","stop","restart","status"]):
        return "Incorrect verb"       
    cmd = "ipsec " + arg
    result = execute_command(cmd)
    return result

def add_keyboard(text, options):
    return {
        'text': text,
        'keyboard': ReplyKeyboardMarkup(
            keyboard = [list(map(lambda x: KeyboardButton(text = x), options))],
            resize_keyboard = True,
            one_time_keyboard = True
        )
    }

def handle_add(args):
    if(len(args) == 1):
        return cmd_add_torrent(magnet=args[0])
    if(len(args) == 2):
        return cmd_add_torrent(args[0], args[1])
    return 'Incorrect number of arguments, use: /add <magnet> [folder]'

def handle_start(args):
    if(len(args) > 1):
        return 'Incorrect number of arguments, use: /start [torrents]'
    torrents = "all" if len(args) == 0 else args[0]
    return cmd_manage_torrent("--start", torrents)

def handle_speed_limit(args):
    keyboard_options =  ['/speed_limit on', '/speed_limit off']
    if(len(args) != 1):
        return add_keyboard('Incorrect number of arguments, use: /speed_limit <on|off>', keyboard_options)
    cmd = args[0]
    if(cmd not in ["on", "off"]):
        return add_keyboard('Wrong argument, use: /speed_limit <on|off>', keyboard_options)
    command = {
        "on": "-as",
        "off": "-AS"
    }[cmd]
    return cmd_torrent(command)

def handle_stop(args):
    if(len(args) > 1):
        return 'Incorrect number of arguments, use: /stop [torrents]'
    torrents = "all" if len(args) == 0 else args[0]
    return cmd_manage_torrent("--stop", torrents)

def handle_remove(args):
    if(len(args) > 1):
        return 'Incorrect number of arguments, use: /delete [torrents]'
    torrents = "all" if len(args) == 0 else args[0]
    return cmd_manage_torrent("--remove", torrents)

def handle_list(args):
    return cmd_torrent("--list")

def handle_vpn(args):
    if(len(args) == 1):
        return cmd_ipsec(args[0])
    
    return add_keyboard('Incorrect number of arguments, use: /vpn <status|start|restart|stop>', ['/vpn status', '/vpn start', '/vpn restart', '/vpn stop'])

def handle_unknown(args):
    return 'Unknown command'

def send_reply(reply, chat_id):
    txt = reply if isinstance(reply,str) else reply['text']
    markup = None if isinstance(reply,str) else reply['keyboard']
    markup = ReplyKeyboardRemove() if markup == None else markup
    telegram_bot.sendMessage(chat_id, txt, reply_markup = markup)

def action(msg):
    user_id = msg['from']['id']
    chat_id = msg['chat']['id']
    if(user_id not in AUTHORIZED_USERS):
        telegram_bot.sendMessage(chat_id, 'Not authorized ' + str(user_id))
        return
    
    try:
        command = msg['text'].split(' ')
        reply = {
                '/add': handle_add,
                '/remove': handle_remove,
                '/start': handle_start,
                '/speed_limit': handle_speed_limit,
                '/stop': handle_stop,
                '/list': handle_list,
                '/vpn': handle_vpn
            }.get(command[0], handle_unknown)(command[1:]) if (len(command) > 0) else "Where's a command?"
    except Exception as e:
        reply = 'Ups, error: ' + str(e)
    reply = "<empty>" if not reply else reply 
    send_reply(reply, chat_id)

def main():
    global telegram_bot
    telegram_bot = telepot.Bot(TOKEN)
    MessageLoop(telegram_bot, action).run_as_thread()
    while(1):
        time.sleep(10)
    
if __name__ == '__main__':
    myname=os.path.basename(sys.argv[0])
    pidfile='/tmp/%s' % myname       # any name
    daemon = Daemonize(app=myname,pid=pidfile, action=main)
    daemon.stdout = '/home/osmc/main.stdout.txt' # MUST BE ABSOLUTE PATH
    daemon.stderr = '/home/osmc/main.stderr.txt'
    daemon.start()
