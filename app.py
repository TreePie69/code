from flask import Flask, render_template, request, redirect, url_for, jsonify
from peewee import Model, SqliteDatabase, CharField, IntegerField
import pandas as pd
import random
import os
import matplotlib.pyplot as plt
import io
import base64

# Flask lietotnes inicializācija
app = Flask(__name__)

db = SqliteDatabase('spotify_game.db')

# Datubāzes modelis
class PlayerScore(Model):
    name = CharField()
    score = IntegerField()

    class Meta:
        database = db

# Izveido datubāzi, ja tā vēl neeksistē
db.connect()
db.create_tables([PlayerScore])

# Ielādē Spotify top 500 datus
csv_file = "spotify_top500.csv"
if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
    if df.empty:
        df = pd.DataFrame(columns=["Artist", "MonthlyListeners"])
else:
    df = pd.DataFrame(columns=["Artist", "MonthlyListeners"])

def get_random_artists():
    """Atgriež divus nejaušus māksliniekus."""
    if df.empty or len(df) < 2:
        return [{"Artist": "Nav pieejamu datu", "MonthlyListeners": 0},
                {"Artist": "Lūdzu augšupielādējiet CSV", "MonthlyListeners": 0}]
    artists = df.sample(2).to_dict(orient='records')
    return artists

@app.route('/')
def index():
    """Sākumlapa ar spēli."""
    artists = get_random_artists()
    return render_template('index.html', artist1=artists[0], artist2=artists[1])

@app.route('/guess', methods=['POST'])
def guess():
    """Pārbauda lietotāja izvēli."""
    chosen = request.form['chosen']
    other = request.form['other']
    
    if df.empty or chosen not in df['Artist'].values or other not in df['Artist'].values:
        return render_template('result.html', result='error', chosen=chosen, other=other, chosen_listener=0, other_listener=0)
    
    chosen_listener = df.loc[df['Artist'] == chosen, 'MonthlyListeners'].values[0]
    other_listener = df.loc[df['Artist'] == other, 'MonthlyListeners'].values[0]
    
    result = 'win' if chosen_listener > other_listener else 'lose'
    return render_template('result.html', result=result, chosen=chosen, other=other, chosen_listener=chosen_listener, other_listener=other_listener)

@app.route('/leaderboard')
def leaderboard():
    """Lietotāju rezultātu tabula."""
    scores = PlayerScore.select().order_by(PlayerScore.score.desc()).limit(10)
    return render_template('leaderboard.html', scores=scores)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """CSV datu augšupielāde."""
    if request.method == 'POST':
        file = request.files['file']
        df_new = pd.read_csv(file)
        df_new.to_csv(csv_file, index=False)
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/plot')
def plot():
    """Ģenerē un attēlo histogrammu."""
    if df.empty:
        return "Nav pieejami dati histogrammai. Lūdzu augšupielādējiet CSV."
    
    plt.figure(figsize=(8, 6))
    df['MonthlyListeners'].hist(bins=20)
    plt.xlabel("Mēneša klausītāji")
    plt.ylabel("Mākslinieku skaits")
    plt.title("Spotify Top 500 Izkliede")
    
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    return render_template('plot.html', plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)
