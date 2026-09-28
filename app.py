"""既存のURL・テンプレート・フォーム名を維持したFlaskエントリーポイント。"""
from flask import Flask, render_template, request
from kantei_main import InputError, kantei_kisyu, kantei_uma, validate_kusei

app = Flask(__name__)


def _stars_from_form():
    return [request.form.get(key) for key in ("kusei_nen", "kusei_tuki", "kusei_hi")]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/kakusu_select", methods=["GET", "POST"])
def kakusu_select():
    if request.method != "POST":
        return render_template("index.html")
    try:
        # 共有配列へのappendを廃止。毎回のPOST値だけを次の画面へ渡す。
        data_kusei = list(validate_kusei(*_stars_from_form()))
    except InputError as exc:
        return render_template("errer.html", kotae=["errer", str(exc), exc.value])
    selected = request.form.get("select_form_id")
    if selected == "kisyu":
        return render_template("kisyu_form.html", data_kusei=data_kusei)
    if selected == "uma":
        return render_template("uma_form.html", data_kusei=data_kusei)
    return render_template("no-kakusu.html")


@app.route("/kisyu_form", methods=["GET", "POST"])
def kisyu_form():
    if request.method != "POST":
        return render_template("no-kakusu.html")
    names = [request.form.get(f"kisyu{i}", "") for i in range(1, 19)]
    kotae = kantei_kisyu(names, *_stars_from_form())
    template = "errer.html" if kotae[0] == "errer" else "kisyu_kantei.html"
    return render_template(template, kotae=kotae)


@app.route("/uma_form", methods=["GET", "POST"])
def uma_form():
    if request.method != "POST":
        return render_template("no-kakusu.html")
    names = [request.form.get(f"uma{i}", "") for i in range(1, 19)]
    kotae = kantei_uma(names, *_stars_from_form())
    template = "errer.html" if kotae[0] == "errer" else "uma_kantei.html"
    return render_template(template, kotae=kotae)


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run()
