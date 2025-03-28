from flask import Flask, render_template, request, session
from peewee import Model, SqliteDatabase, CharField, IntegerField
import pandas as pd
import os
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

app = Flask(__name__)
app.secret_key = "your_secret_key"

db = SqliteDatabase('spotify_game.db')

class PlayerScore(Model):
    name = CharField()
    score = IntegerField()
    class Meta:
        database = db

db.connect()
db.create_tables([PlayerScore])

csv_file = "spotify_top500.csv"
if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
    if df.empty:
        df = pd.DataFrame(columns=["Artist", "MonthlyListeners"])
else:
    df = pd.DataFrame(columns=["Artist", "MonthlyListeners"])

def get_random_artists():
    if df.empty or len(df) < 2:
        return [
            {"Artist": "No Data Available", "MonthlyListeners": 0},
            {"Artist": "Please Upload CSV", "MonthlyListeners": 0}
        ]
    return df.sample(2).to_dict(orient='records')

def generate_chart(guessed_listeners, guessed_others, guessed_artists):
    x = np.arange(len(guessed_listeners))
    width = 0.35
    fig, ax = plt.subplots(figsize=(16, 6), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')

    bars_chosen = ax.bar(x - width / 2, guessed_listeners, width, label="Chosen Artist", color="#1E90FF")
    bars_other = ax.bar(x + width / 2, guessed_others, width, label="Other Artist", color="#FF4C4C")

    for i, bar in enumerate(bars_chosen):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h * 0.5, guessed_artists[i][0], ha='center', va='center', fontsize=9, rotation=90, color='white')
        ax.text(bar.get_x() + bar.get_width() / 2, h + 10000, f"{int(h):,}", ha='center', va='bottom', fontsize=9, color='white')

    for i, bar in enumerate(bars_other):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h * 0.5, guessed_artists[i][1], ha='center', va='center', fontsize=9, rotation=90, color='white')
        ax.text(bar.get_x() + bar.get_width() / 2, h + 10000, f"{int(h):,}", ha='center', va='bottom', fontsize=9, color='white')

    ax.set_xticks(x)
    ax.set_xticklabels([f"Guess {i+1}" for i in range(len(guessed_listeners))], color='white')
    ax.set_xlabel("Guess Number", color='white')
    ax.set_ylabel("Monthly Listeners", color='white')
    ax.set_title("Game Progression", color='white')
    ax.legend(facecolor='#1e1e1e', edgecolor='white', labelcolor='white')
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_color('white')

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches="tight", facecolor=fig.get_facecolor())
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode()

@app.route('/')
def index():
    session.setdefault('gradient', 'purple')
    if 'artist1' not in session or 'artist2' not in session:
        artists = get_random_artists()
        session['artist1'], session['artist2'] = artists
    return render_template('index.html',
        artist1=session['artist1'],
        artist2=session['artist2'],
        settings={'gradient': session['gradient']}
    )

@app.route('/game_over')
def game_over():
    score = session.get('correct_guesses', 0)
    guessed_listeners = session.get('guessed_listeners', [])
    guessed_others = session.get('guessed_others', [])
    guessed_artists = session.get('guessed_artists', [])
    plot_url = generate_chart(guessed_listeners, guessed_others, guessed_artists) if guessed_listeners else None
    return render_template('game_over.html',
        score=score,
        plot_url=plot_url,
        settings={'gradient': session.get('gradient', 'purple')}
    )

@app.route('/guess', methods=['POST'])
def guess():
    chosen = request.form['chosen']
    other = request.form['other']
    session.setdefault('gradient', 'purple')

    if df.empty or chosen not in df['Artist'].values or other not in df['Artist'].values:
        return render_template('result.html',
            result='error',
            chosen=chosen,
            other=other,
            chosen_listener=0,
            other_listener=0,
            settings={'gradient': session['gradient']}
        )

    chosen_listener = int(df.loc[df['Artist'] == chosen, 'MonthlyListeners'].values[0])
    other_listener = int(df.loc[df['Artist'] == other, 'MonthlyListeners'].values[0])

    session.setdefault('guessed_listeners', []).append(chosen_listener)
    session.setdefault('guessed_others', []).append(other_listener)
    session.setdefault('guessed_artists', []).append((chosen, other))
    session.setdefault('correct_guesses', 0)

    if chosen_listener > other_listener:
        session['correct_guesses'] += 1
        new_artists = get_random_artists()
        session['artist1'], session['artist2'] = new_artists
        return render_template('index.html',
            artist1=session['artist1'],
            artist2=session['artist2'],
            score=session['correct_guesses'],
            settings={'gradient': session['gradient']}
        )

    score = session['correct_guesses']
    guessed_listeners = session['guessed_listeners']
    guessed_others = session['guessed_others']
    guessed_artists = session['guessed_artists']
    plot_url = generate_chart(guessed_listeners, guessed_others, guessed_artists) if guessed_listeners else None
    gradient = session.get('gradient', 'purple')
    session.clear()
    session['gradient'] = gradient

    return render_template('game_over.html',
        score=score,
        plot_url=plot_url,
        settings={'gradient': gradient}
    )

if __name__ == '__main__':
    app.run(debug=True)