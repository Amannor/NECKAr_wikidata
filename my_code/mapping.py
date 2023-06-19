from datetime import datetime
from pathlib import Path
import json
import typing
from collections import Counter

ENTITIES_TASK_DIR = r"C:\job\iahlt\tasks\wikidata_entities"
ONTOLOGY_TASK_DIR = Path(ENTITIES_TASK_DIR, "ontology_mapping")
WIKI_SUGGESTIONS_DIR = Path(ENTITIES_TASK_DIR, "entities_to_wiki_suggestions")
def create_mapping_file():
    json_path = Path(ONTOLOGY_TASK_DIR, "WikidataNE_20170320_NECKAR_1_0.json")
    data = []
    with open(json_path, 'r', encoding="utf8") as file:  # 'r'
        for line in file:
            data.append(json.loads(line))
    print(data)

    q_id_to_data = {}
    while len(data) > 0:
        cur_item = data.pop()
        q_id_to_data[cur_item['id']] = cur_item

    with open('q_id_to_data.json', 'w') as fp:
        json.dump(q_id_to_data, fp)

def read_mapping_file() -> typing.Dict[str, object]:
    q_id_to_data_path = Path(ONTOLOGY_TASK_DIR, "q_id_to_data.json")
    with open(q_id_to_data_path) as json_file:
        q_id_to_data = json.load(json_file)
    return q_id_to_data

def read_ids_to_labels_file() -> typing.Dict[str, str]:
    res = {}
    with open("our_q_ids_to_labels.json") as json_file:
        res = json.load(json_file)
    return res

def get_our_q_ids() -> typing.Set[str]:
    q_ids = set()
    for f in WIKI_SUGGESTIONS_DIR.glob("entities_to_wiki_suggestions_*.json"):
        with open(f) as json_file:
            wiki_suggestions = json.load(json_file)
        for v in wiki_suggestions.values():
            q_ids.update([i["id"] for i in v])
    return q_ids

print(f"{datetime.now()} Start")

should_create_mapping_file = False
if should_create_mapping_file:
    create_mapping_file()

our_q_ids = get_our_q_ids()

should_create_ids_to_labels_file = False
if should_create_ids_to_labels_file:
    q_id_to_data = read_mapping_file()
    our_q_ids_to_labels = {q_id: q_id_to_data[q_id]["neClass"] for q_id in our_q_ids if q_id in q_id_to_data}
    with open('our_q_ids_to_labels.json', 'w') as fp:
        json.dump(our_q_ids_to_labels, fp, indent=2)

our_q_ids_to_labels = read_ids_to_labels_file()
print(f"Labels count: {Counter(our_q_ids_to_labels.values())}")
print(f"len(our_q_ids_to_labels): {len(our_q_ids_to_labels)} len(our_q_ids) {len(our_q_ids)}")




print(f"{datetime.now()} FIN")
