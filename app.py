from flask import Flask, render_template, jsonify, request, session
import json, random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = BASE_DIR / "questions.json"

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"), static_url_path="/static")
app.secret_key = "dev-key"
app.config["JSON_AS_ASCII"] = False


def load_questions():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError("questions.json must be a JSON array.")
    questions = []
    for i, q in enumerate(raw):
        if not isinstance(q, dict):
            continue
        q = dict(q)
        q["id"] = i
        # 兜底字段
        q.setdefault("category", "未分類")
        q.setdefault("examples", [])
        questions.append(q)
    return questions


QUESTIONS = load_questions()


def categories():
    return sorted({q.get("category", "未分類") for q in QUESTIONS})


def ensure_session():
    session.setdefault("score", 0)
    session.setdefault("total", 0)
    session.setdefault("wrong_ids", [])  # 错题本：题目id数组
    session.setdefault("queues", {})     # 不重复：每个(模式+分类)一个队列


def key_for(mode: str, cat: str) -> str:
    return f"{mode}::{cat}"


def build_pool(mode: str, cat: str):
    """根据模式/分类构造可选题池（列表元素是题目id）"""
    if mode == "wrong":
        ids = [i for i in session.get("wrong_ids", []) if 0 <= i < len(QUESTIONS)]
    else:
        ids = list(range(len(QUESTIONS)))

    if cat != "all":
        ids = [i for i in ids if QUESTIONS[i].get("category") == cat]

    return ids


def pop_next_id(mode: str, cat: str):
    """
    不重复出题：
    - 每个(mode, cat)维护一个队列（打乱后的题目id列表）
    - 用完了就自动重建
    """
    k = key_for(mode, cat)
    queues = session.get("queues", {})
    q = queues.get(k)

    if not isinstance(q, list) or len(q) == 0:
        pool = build_pool(mode, cat)
        if not pool:
            return None
        random.shuffle(pool)
        q = pool

    next_id = q.pop()
    queues[k] = q
    session["queues"] = queues
    return next_id


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/categories")
def api_categories():
    return jsonify({"categories": categories()})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    ensure_session()
    session["score"] = 0
    session["total"] = 0
    # 注意：不清空错题本、不清空队列（你也可以选择清空）
    return jsonify({"ok": True, "stats": {"score": 0, "total": 0, "wrong_count": len(session["wrong_ids"])}})


@app.route("/api/wrong/clear", methods=["POST"])
def api_wrong_clear():
    ensure_session()
    session["wrong_ids"] = []
    # 清空“错题模式”的队列，避免还出旧错题
    queues = session.get("queues", {})
    for k in list(queues.keys()):
        if k.startswith("wrong::"):
            queues.pop(k, None)
    session["queues"] = queues
    return jsonify({"ok": True, "wrong_count": 0})


@app.route("/api/next")
def api_next():
    """
    GET /api/next?category=all&mode=all
    mode=all / mode=wrong
    """
    ensure_session()
    cat = request.args.get("category", "all")
    mode = request.args.get("mode", "all")
    if mode not in ("all", "wrong"):
        mode = "all"

    qid = pop_next_id(mode, cat)
    if qid is None:
        msg = "No questions in this category" if mode == "all" else "错题本里没有题（或该分类下没有错题）"
        return jsonify({"error": msg}), 400

    q = QUESTIONS[qid]
    # 不返回 correct，避免前端直接拿到答案
    return jsonify({
        "id": q["id"],
        "prompt": q["prompt"],
        "choices": q["choices"],
        "category": q.get("category", "未分類"),
        "examples": q.get("examples", []),
        "wrong_count": len(session["wrong_ids"]),
        "mode": mode
    })


@app.route("/api/answer", methods=["POST"])
def api_answer():
    """
    POST JSON: { "id": 0, "choice": 2 }
    """
    ensure_session()
    body = request.get_json(silent=True) or {}
    qid = body.get("id")
    choice = body.get("choice")

    if not isinstance(qid, int) or not isinstance(choice, int):
        return jsonify({"error": "id and choice must be integers"}), 400
    if qid < 0 or qid >= len(QUESTIONS):
        return jsonify({"error": "invalid id"}), 400

    q = QUESTIONS[qid]
    if not isinstance(q.get("choices"), list) or len(q["choices"]) == 0:
        return jsonify({"error": "invalid question choices"}), 400
    if choice < 0 or choice >= len(q["choices"]):
        return jsonify({"error": "invalid choice index"}), 400

    correct_index = q["correct"]
    is_correct = (choice == correct_index)

    session["total"] += 1
    if is_correct:
        session["score"] += 1

    # 错题本：错了加入；对了移除（越练越少）
    wrong_ids = session.get("wrong_ids", [])
    if not is_correct:
        if qid not in wrong_ids:
            wrong_ids.append(qid)
    else:
        if qid in wrong_ids:
            wrong_ids.remove(qid)
    session["wrong_ids"] = wrong_ids

    return jsonify({
        "correct": is_correct,
        "correctIndex": correct_index,
        "correctText": q["choices"][correct_index],
        "examples": q.get("examples", []),
        "stats": {
            "score": session["score"],
            "total": session["total"],
            "wrong_count": len(session["wrong_ids"])
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000,debug=True)