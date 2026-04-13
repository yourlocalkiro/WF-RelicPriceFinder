from flask import Flask, render_template, request
from core import get_top_items, CACHE

app = Flask(__name__)


@app.route("/")
def home():
    # Query params
    min_price = int(request.args.get("min_price", 0))
    sort = request.args.get("sort", "desc")

    refresh = request.args.get("refresh")

    # ✅ CLEAR CACHE if refresh pressed
    if refresh:
        CACHE["data"] = None
        CACHE["timestamp"] = 0
        print("Cache cleared!")

    data = get_top_items()

    items = data["items"]
    best_relics = data["best_relics"]

    # ✅ Filter
    items = [i for i in items if i["price"] >= min_price]

    # ✅ Sort toggle
    reverse = True if sort == "desc" else False
    items = sorted(items, key=lambda x: x["price"], reverse=reverse)

    return render_template(
        "index.html",
        items=items,
        best_relics=best_relics,
        min_price=min_price,
        sort=sort
    )


if __name__ == "__main__":
    app.run(debug=True)