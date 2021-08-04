import botsettings
import re

def hi(query, msg, db):
    return "ello"

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
        return f"Found {len(good)} results:\n\n{lines}"
    else:
        return False


def list_(query, msg, db):
    def describe(doc):
        return f"#{doc['idx']} from {doc['whom']}\n{doc['title']}\n{doc['url']}\n{doc['content']}..."
    docs = db.documents
    lines = "\n\n".join([describe(x) for x in db.documents])
    return f"{len(docs)} documents:\n" + lines


trigger_list = [
    {"term": "add", "callback": add},
    {"term": "hello|hi", "callback": hi},
    {"term": "list", "callback": list_}
]
fallback_list = [
    search
]


