import re
import sys

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import scipy

import botsettings

def hi(query, msg, db):
    if db.count() == 0:
        return "👋 ello. im hungry."
    else:
        return "👋 ello.."


def add(query, msg, db):
    urlpat = re.compile("(http(s)?://.+\w)")
    match = urlpat.search(query)
    if match:
        print('add(): got url match', match, msg)
        whom = msg.effective_user.username
        item = db.add(match[1], whom)
        return f"Added:\n{repr(item)}"
    else:
        return "couldnt find a link in your message"


def search(query, msg, db):
    results = db.search(query)
    print('search() results', results)
    if len(results) == 0:
        return "✖️ No results"

    good = [x for x in results if x["distance"] < botsettings.MAX_DISTANCE]
    if good:
        lines = "\n".join([
            (
                f"{item['title']}" +
                (f" (dist={item['distance']})\n" if botsettings.DEBUG else "\n") +
                f"{item['url']}\n"
            )
            for item in good
        ])
        return f"👍 Found {len(good)} results:\n\n{lines}"
    else:
        if botsettings.DEBUG:
            lines = "\n".join([f"{item['title']} (d={item['distance']})\n" for item in results])
            return f"👎 <b>No good results</b>. Closest:\n\n{lines}"
        else:
            return False


def list_(query, msg, db):
    def describe(doc):
        return f"<u>#{doc['idx']}</u> from <b>{doc['whom']}</b>\n{doc['title']}\n{doc['url']}\n{doc['content'][:64]}..."
    docs = db.documents
    lines = "\n\n".join([describe(x) for x in db.documents])
    return f"📜 **{len(docs)} documents**:\n" + lines


def debug(query, msg, db):
    m = re.search('"(.+)" vs "(.+)"', query)
    if m:
        a = m[1]
        b = m[2]
        emb1 = db.embedding(a)
        emb2 = db.embedding(b)
        emb_delta = emb1 - emb2
        fig = plt.figure(figsize=(8,6))
        plt.hist(emb1, bins=100, alpha=0.5, label=a)
        plt.hist(emb2, bins=100, alpha=0.5, label=b)
        plt.hist(emb_delta, bins=100, alpha=0.5, label="diff")
        fig.canvas.draw()
        # chart = np.fromstring(fig.canvas.tostring_rgb(),dtype=np.uint8)
        chart = Image.frombytes('RGB', fig.canvas.get_width_height(),fig.canvas.tostring_rgb())
        stats1 = repr(scipy.stats.describe(emb1))
        stats2 = repr(scipy.stats.describe(emb2))
        l2dist = np.linalg.norm(emb1-emb2)
        return {'image': chart, 'caption': f'bert embedding of "{a}" - "{b}"\nl2 dist: {l2dist}\n{stats1}\n{stats2}'}
    else:
        query = query.replace('debug', '')
        emb = db.embedding(query)
        stats = repr(scipy.stats.describe(emb))
        return {'array': emb, 'caption': f'bert embedding for "{query}"\n{stats}'}


def reset(query, msg, db):
    msg.message.reply_text("goodbye, cruel world..")
    return {'exit': True}


def help_(query, msg, db):
    oldster = "👨‍🦳"
    name = botsettings.DISPLAY_NAME
    lines = [f"{name} {x['term']}" for x in trigger_list]
    lines = "\n".join(lines)
    return f"{oldster} i understand these:\n\n{lines}"

trigger_list = [
    {"term": "add", "callback": add},
    {"term": "hello", "callback": hi},
    {"term": "hi", "callback": hi},
    {"term": "help", "callback": help_},
    {"term": "list", "callback": list_},
    {"term": "debug", "callback": debug},
    {"term": "self destruct", "callback": reset}
]
fallback_list = [
    search
]


