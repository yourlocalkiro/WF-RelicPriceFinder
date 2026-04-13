from flask import Flask, render_template
from core import get_top_items

app = Flask(__name__)


@app.route("/")
def home():
    data = get_top_items()
    return render_template("index.html", data=data)


if __name__ == "__main__":
    app.run(debug=True)