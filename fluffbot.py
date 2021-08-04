import json
import os
import re

import torch
from sentence_transformers import SentenceTransformer
# Used to create and store the Faiss index.
import faiss
import numpy as np
import pickle
import goose3
import urllib.request
import logging

from telegram import Update, ForceReply
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

def slurp_url(url):
    g = goose3.Goose()
    g.browser_user_agent = botsettings.USER_AGENT
    info = g.extract(url=url)
    return info

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
        content = art.cleaned_text
        content_start = content[:256]
        embedding = encode(content, self.model)
        doc_id = len(self.documents)
        self.index.add_with_ids(embedding, np.array([doc_id]))
        idx = len(self.documents)
        item = {"idx": idx, "title": art.title, "content": content_start, "url": url, "whom": whom}
        self.documents.append(item)
        return item

    def search(self, term):
        te = encode(term, self.model)
        dist, idxs = self.index.search(te, k=3)
        dist = dist[0].tolist();
        idxs = idxs[0].tolist();
        print('results', dist, idxs)
        results = []
        for n, idx in enumerate(idxs):
            item = self.documents[idx]
            print(item)
            results.append({**item, "rank": n, "id": idx, "distance": int(dist[n])})
        return results



def http(url):
    contents = urllib.request.urlopen(url).read()
    return contents


def encode(text, model):
    e = model.encode([text], show_progress_bar=False)
    return np.array([e[0]])


def find_trigger(query, msg, db):
    response = False
    for trigger in bottriggers.trigger_list:
        if "term" in trigger:
            term = trigger["term"]
            term_re = re.compile(term, flags=re.I)
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


def handle_tg_msg(update, context, model, db):
    print(update)
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
            update.message.reply_text(response)
        else:
            response = try_fallback(query_without_botname, update, db)
            if response:
                print('got fallback response', response)
                update.message.reply_text(response)
            else:
                if botsettings.DEBUG:
                    print('unsure what to do, echoing..')
                    newmsg = f"msg\n```{txt}```"
                    update.message.reply_text(newmsg)
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
    if not db.load():
        for x in sample_links:
            item = db.add(x, 'system-demo')
            print('created', item)
 
    #index = make_db(embs2, model)
    bot = start_bot(model, db)


main()
