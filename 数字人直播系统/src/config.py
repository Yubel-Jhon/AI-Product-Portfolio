"""config.py — 配置层：模特 / 语料库都是「文件夹 mod」，丢进去就能被扫到、能切换。

模特（一个文件夹一个）：
  live2d_page/Resources/models/<id>/
    model.json    # {"name", "type": "live2d", "model": "X.model3.json", "voice", "pitch", "rate", "zoom", "y"}
    或 type "puppet"：# {"name", "type": "puppet", "image": "body.png", "face": "face.json", ...}
    （还有模型本体文件：moc3/texture/motion，或 body.png/face.json）

语料库（一个文件夹一个）：
  corpora/<id>/
    corpus.json   # {"name", "persona", "faq": "faq.json", "loop_lines": [...]}
    faq.json      # 知识库问答

当前组合存在 state.json；switch() 改状态并返回最新组合。
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
# 打包成桌面应用后 src/ 是只读的（在安装目录里），state.json / chroma_db 要写到可写目录。
# 默认还是 BASE（源码跑不变），打包时 Electron 用 ADH_DATA_DIR 指向用户数据目录。
DATA_DIR = os.environ.get("ADH_DATA_DIR") or BASE
MODELS_DIR = os.path.join(BASE, "live2d_page", "Resources", "models")
CORPORA_DIR = os.path.join(BASE, "corpora")
STATE_PATH = os.path.join(DATA_DIR, "state.json")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---- 模特 ----
def list_models():
    """扫描 models/ 下每个子文件夹的 model.json，返回带 id 的列表。"""
    out = []
    if not os.path.isdir(MODELS_DIR):
        return out
    for name in sorted(os.listdir(MODELS_DIR)):
        cfg_path = os.path.join(MODELS_DIR, name, "model.json")
        if not os.path.isfile(cfg_path):
            continue
        try:
            m = _load_json(cfg_path)
        except Exception as e:
            print(f"[config] 跳过坏模特 {name}：{e}")
            continue
        m["id"] = name
        out.append(m)
    return out


def get_model(model_id):
    for m in list_models():
        if m["id"] == model_id:
            return m
    return None


# ---- 语料库 ----
def list_corpora():
    out = []
    if not os.path.isdir(CORPORA_DIR):
        return out
    for name in sorted(os.listdir(CORPORA_DIR)):
        cfg_path = os.path.join(CORPORA_DIR, name, "corpus.json")
        if not os.path.isfile(cfg_path):
            continue
        try:
            c = _load_json(cfg_path)
        except Exception as e:
            print(f"[config] 跳过坏语料 {name}：{e}")
            continue
        c["id"] = name
        out.append(c)
    return out


def get_corpus(corpus_id):
    for c in list_corpora():
        if c["id"] == corpus_id:
            return c
    return None


def corpus_faq_path(corpus_id):
    """语料库的 faq.json 绝对路径。"""
    c = get_corpus(corpus_id)
    if not c:
        return None
    return os.path.join(CORPORA_DIR, corpus_id, c.get("faq", "faq.json"))


# ---- 当前组合（state.json 持久化）----
def _load_state():
    if os.path.isfile(STATE_PATH):
        try:
            return _load_json(STATE_PATH)
        except Exception:
            pass
    return {}


def _save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_active_ids():
    """当前 (model_id, corpus_id)，无状态时取列表第一个。"""
    models = list_models()
    corpora = list_corpora()
    state = _load_state()
    model_id = state.get("model_id")
    corpus_id = state.get("corpus_id")
    if not get_model(model_id) and models:
        model_id = models[0]["id"]
    if not get_corpus(corpus_id) and corpora:
        corpus_id = corpora[0]["id"]
    return model_id, corpus_id


def get_active():
    model_id, corpus_id = get_active_ids()
    return {"model_id": model_id, "corpus_id": corpus_id}


def get_active_model():
    return get_model(get_active_ids()[0])


def get_active_corpus():
    return get_corpus(get_active_ids()[1])


def switch(model_id=None, corpus_id=None):
    """切换模特 / 语料（传哪个换哪个），持久化并返回最新组合。"""
    state = _load_state()
    if model_id and get_model(model_id):
        state["model_id"] = model_id
    if corpus_id and get_corpus(corpus_id):
        state["corpus_id"] = corpus_id
    _save_state(state)
    return get_active()
