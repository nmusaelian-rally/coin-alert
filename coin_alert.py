#!/usr/local/bin/python3.5

#################################################################################################
#
#  coin-alert.py -  email alert if coin price changes above threshold
#
USAGE = """
Usage: python coinalert.py <coin><interval><threshold> <coin2><interval><threshold>
       at least one argument <coin><interval><threshold> is expected,
       valid values for interval: 1h, 24h, 7d
       usage example:
       python coin-alert.py burst1h5 bitcoin24h10
"""
#################################################################################################


import os, sys
from smtplib import SMTP, SMTPException

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import re
import requests
from datetime import datetime
from collections import OrderedDict

PATTERN    = r"^[a-zA-Z]+\d{1,2}(h|d)\d+$"

SENDER     = os.environ['SENDER']
RECIPIENT  = os.environ['RECIPIENT']
SECRET     = os.environ['SECRET']

SMTP_PARMS = {'server': 'smtp.mail.yahoo.com',
              'port': 587,
              'username': SENDER,
              'password': SECRET
              }

def matchPattern(a):
    pattern = re.compile(PATTERN)
    return pattern.match(a)

def parseArgs(a):
    '''
    return an object that looks like this:
     coin = {'name': 'burst', 'interval': '24h', 'threshold': 10}
    '''
    coin = {}
    parts = re.split(r'(\d+h)|(\d+d)', a) # => ['burst', '24h', None, '10'] or ['burst', None, '7d', '10']
    coin['name']      = parts[0].lower()
    coin['interval']  = parts[1] if parts[1] else parts[2]
    coin['threshold'] = int(parts[3])
    return coin

def getCoinTicker(coin_name):
    url = 'https://api.coinmarketcap.com/v1/ticker/%s/' % coin_name
    r = requests.get(url)
    return r.json()[0]

def getPercentChange(coin, result):

    percent_change = 0.00
    if coin['interval'] == '1h':
        percent_change = float(result['percent_change_1h'])
    elif coin['interval'] == '24h':
        percent_change = float(result['percent_change_24h'])
    elif coin['interval'] == '7d':
        percent_change = float(result['percent_change_7d'])

    return percent_change


def orderKeys(result):
    key_order = ["id", "name", "symbol", "rank", "price_usd", "price_btc", "24h_volume_usd",
                 "market_cap_usd", "available_supply", "total_supply", "max_supply",
                 "percent_change_1h", "percent_change_24h", "percent_change_7d", "last_updated"]

    ordered_result = OrderedDict([(key, result[key]) for key in key_order])
    return ordered_result


def prepareMessage(d):
    result = "<table>"
    for key, value in d.items():
        if key == "last_updated":
            value = datetime.fromtimestamp(float(value)).strftime('%c')
        result += """\
        <tr>
           <th> %s </th>
           <td> %s </td>
        </tr>
        """ % (key, value)
    result += "</table>"

    text = "~~~~~" * 10
    html = """\
    <html>
        <head></head>
        <body>
            %s
        </body>
    """ % result

    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    return part1, part2



def main(args):
    options = [opt for opt in args if opt.startswith('--')]
    args = [arg for arg in args if arg not in options]

    if not args:
        print(USAGE)
        exit(1)

    coins   = []

    for a in args:
        if matchPattern(a):
            coins.append(parseArgs(a))
        else:
            print("%s does not match expected pattern %s" %(a, PATTERN), file=sys.stderr)

    alert = False
    subject = ""
    msg = MIMEMultipart()
    msg['From']    = SENDER
    msg['To']      = RECIPIENT

    for coin in coins:
        result = getCoinTicker(coin['name'])
        ordered_result = orderKeys(result)
        part1, part2 = prepareMessage(ordered_result)
        msg.attach(part1)
        msg.attach(part2)
        direction = "" # UP or DOWN
        percent_change = getPercentChange(coin, result)
        if abs(percent_change) >= coin['threshold']:
            direction = "UP" if percent_change > 0 else "DOWN"
            subject += "%s is %s %d %% in %s..." % (result['symbol'], direction,  abs(percent_change), coin['interval'])
            alert = True
        else:
            print("percent_change for %s is below threshold, no email will be sent" %coin['name'])

    if alert:
        msg['Subject'] = subject
        try:
            smtp = SMTP(SMTP_PARMS['server'], SMTP_PARMS['port'])
            smtp.set_debuglevel(True)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.esmtp_features['auth'] = 'LOGIN PLAIN'
            smtp.login(SMTP_PARMS['username'], SMTP_PARMS['password'])
            message = msg.as_string()
            smtp.sendmail(SENDER, RECIPIENT, message)
            smtp.quit()
            print("Successfully sent email")
        except SMTPException as exc:
            print("ERROR:", exc)


if __name__ == '__main__':
    main(sys.argv[1:])