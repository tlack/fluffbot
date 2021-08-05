import json
import os
import re
import time

import torch
from sentence_transformers import SentenceTransformer
# Used to create and store the Faiss index.
import faiss
import numpy as np
import pickle
import goose3
import scipy
import urllib.request
import logging

from PIL import Image
from matplotlib import cm

from telegram import Update, ForceReply
from telegram.constants import *
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import botsettings
import bottriggers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )
logger = logging.getLogger(__name__)

sample_links = [
    'https://randomnerdtutorials.com/esp32-pwm-arduino-ide/',
    'https://www.electronicshub.org/esp32-pwm-tutorial/',
    'https://diyi0t.com/i2s-sound-tutorial-for-esp32/',
    'https://learn.sparkfun.com/tutorials/i2s-audio-breakout-hookup-guide/all',
]

class DocumentDB:
    def __init__(self, shape, model):
        index = faiss.IndexFlatL2(shape)
        self.index = faiss.IndexIDMap(index)
        self.model = model
        self.documents = []

    def load(self):
        if os.path.exists("documents.json"):
            self.documents = json.loads(open("documents.json").read())
            return True
        else:
            print("DocumentDB.load(): no documents.json")
            return False

    def add(self, url, whom):
        # print(art.title)
        # print(art.cleaned_text)
        art = slurp_url(url)
        content = f"{art.title}. {art.cleaned_text}."
        content_start = content[:256]
        embedding = encode(content, self.model)
        embedding_a = np.array([embedding])
        doc_id = len(self.documents)
        self.index.add_with_ids(embedding_a, np.array([doc_id]))
        idx = len(self.documents)
        item = {"idx": idx, "title": art.title, "content": content_start, "url": url, "whom": whom}
        self.documents.append(item)
        return item

    def count(self):
        return len(self.documents)

    def embedding(self, term):
        return encode(term, self.model)

    def search(self, term):
        emb = encode(term, self.model)
        emb_a = np.array([emb])
        n_results = len(self.documents)
        if n_results == 0:
            return []
        elif n_results > botsettings.N_RESULTS:
            n_results = botsettings.N_RESULTS
        dist, idxs = self.index.search(emb_a, k=n_results)
        dist = dist[0].tolist();
        idxs = idxs[0].tolist();
        print('results', dist, idxs)
        results = []
        for n, idx in enumerate(idxs):
            item = self.documents[idx]
            print(item)
            results.append({**item, "rank": n, "id": idx, "distance": int(dist[n])})
        return results


def slurp_url(url):
    g = goose3.Goose()
    g.browser_user_agent = botsettings.USER_AGENT
    info = g.extract(url=url)
    return info


def http(url):
    contents = urllib.request.urlopen(url).read()
    return contents


def encode(text, model):
    e = model.encode([text], show_progress_bar=False)
    emb = e[0]
    if botsettings.NORMALIZE == "01":
        emb = (emb - np.min(emb))/np.ptp(emb)
    elif botsettings.NORMALIZE == "-1+1":
        emb = 2.*(emb - np.min(emb))/np.ptp(emb)-1
    return emb


def find_trigger(query, msg, db):
    response = False
    for trigger in bottriggers.trigger_list:
        if "term" in trigger:
            term = trigger["term"]
            term_re = re.compile(f"\\b{term}\\b", flags=re.I)
            if term_re.search(query):
                print('found handler', term)
                response = trigger["callback"](query, msg, db)
                break
            else:
                print('didnt match', term_re)
    return response


def try_fallback(query, msg, db):
    response = False
    for callback in bottriggers.fallback_list:
        response = callback(query, msg, db)
    return response

def image_from_array(array):
    w = 32 
    h = 24
    array = np.reshape(array, (w, h))
    im = Image.fromarray(np.uint8(cm.gist_earth(array)*255))
    im = im.resize((w * 16, h * 16), Image.ANTIALIAS)
    rgb_im = im.convert('RGB')
    #PIL_image = Image.fromarray(numpy_image.astype('uint8'), 'RGB')
    #plt.imsave(filename, np_array, cmap='Greys')
    return rgb_im


def just_exit():
    print('exiting..')
    time.sleep(1)
    os._exit(0)


def send_image_reply(update, image, caption):
    from io import BytesIO
    bio = BytesIO()
    bio.name = 'array.jpeg'
    image.save(bio, 'JPEG')
    bio.seek(0)
    update.message.reply_photo(bio, caption=caption)


def send_text_reply(update, text):
    update.message.reply_text(text, parse_mode=PARSEMODE_HTML)


def send_response(update, response):
    if type(response) == type({}):  #XXX nonidiomatic
        if "array" in response:
            img = response["array"]
            if type(img) == np.ndarray:
                img = image_from_array(img)
            send_image_reply(update, img, response.get("caption", ""))
        elif "exit" in response:
            just_exit()
        elif "image" in response:
            img = response["image"]
            send_image_reply(update, img, response.get("caption", ""))
        elif "text" in response:
            send_text_reply(update, response["text"])
    else:
        send_text_reply(update, response)


def handle_tg_msg(update, context, model, db):
    print('handle_tg_msg', update)
    if update.edited_message:
        txt = update.edited_message.text
        update.message = update.edited_message
    else:
        txt = update.message.text
    for_me = False
    query_without_botname = txt
    match_txt = txt.replace("@", "").lower()
    for name in botsettings.RESPOND_TO:
        name_re = re.compile(f"\w?@?{name}\w?", flags=re.I)
        if name_re.search(txt):
            query_without_botname = re.sub(name_re, "", txt).strip()
            # query_without_botname = txt
            for_me = True
            break

    if for_me:
        print('msg for me:', query_without_botname)
        response = find_trigger(query_without_botname, update, db)
        if response:
            print('got response', response)
            send_response(update, response)
        else:
            response = try_fallback(query_without_botname, update, db)
            if response:
                print('got fallback response', response)
                send_response(update, response)
            else:
                if botsettings.DEBUG:
                    print('unsure what to do, echoing..')
                    newmsg = f"msg\n```{txt}```"
                    send_response(update, response)
    else:
        print('not for me:', txt)


def start_bot(model, db):
    updater = Updater(botsettings.BOT_KEY)
    dispatcher = updater.dispatcher

    handler_lambda = lambda msg, context, mod=model, db=db: handle_tg_msg(msg, context, mod, db)

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handler_lambda))
    updater.start_polling()
    updater.idle()


def main():
    model = SentenceTransformer(botsettings.BERT_MODEL)
    test_emb = model.encode(["Test"], show_progress_bar=False)
    shape = test_emb.shape[1]
    db = DocumentDB(shape, model)

    if botsettings.LOAD_DEMO_LINKS and not db.load():
        for x in sample_links:
            item = db.add(x, 'system-demo')
            print('created', item)
 
    #index = make_db(embs2, model)
    bot = start_bot(model, db)


main()
