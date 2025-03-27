from flask import Flask, render_template, request, redirect, url_for, session
from peewee import Model, SqliteDatabase, CharField, IntegerField
import pandas as pd
import os
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database setup
db = SqliteDatabase('spotify_game.db')

class PlayerScore(Model):
    name = CharField()
    score = IntegerField()

    class Meta:
        database = db

db.connect()
db.create_tables([PlayerScore])

# Load CSV data
csv_file = "spotify_top500.csv"
if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
    if df.empty:
        df = pd.DataFrame(columns=["Artist", "MonthlyListeners"])
else:
    df = pd.DataFrame(columns=["Artist", "MonthlyListeners"])

# Function to get two random artists
def get_random_artists():
    if df.empty or len(df) < 2:
        return [{"Artist": "No Data Available", "MonthlyListeners": 0},
                {"Artist": "Please Upload CSV", "MonthlyListeners": 0}]
    return df.sample(2).to_dict(orient='records')

@app.route('/')
def index():
    session.clear()
    artists = get_random_artists()
    return render_template('index.html', artist1=artists[0], artist2=artists[1])

@app.route('/guess', methods=['POST'])
def guess():
    chosen = request.form['chosen']
    other = request.form['other']

    if df.empty or chosen not in df['Artist'].values or other not in df['Artist'].values:
        return render_template('result.html', result='error', chosen=chosen, other=other, chosen_listener=0, other_listener=0)

    chosen_listener = int(df.loc[df['Artist'] == chosen, 'MonthlyListeners'].values[0])
    other_listener = int(df.loc[df['Artist'] == other, 'MonthlyListeners'].values[0])

    session.setdefault('guessed_listeners', [])
    session.setdefault('guessed_others', [])
    session.setdefault('guessed_artists', [])
    session.setdefault('correct_guesses', 0)

    session['guessed_listeners'].append(chosen_listener)
    session['guessed_others'].append(other_listener)
    session['guessed_artists'].append((chosen, other))

    if chosen_listener > other_listener:
        session['correct_guesses'] += 1
        new_artists = get_random_artists()
        return render_template('index.html', artist1=new_artists[0], artist2=new_artists[1], score=session['correct_guesses'])

    # Game over - Generate Seaborn chart
    score = session.get('correct_guesses', 0)
    guessed_listeners = session.get('guessed_listeners', [])
    guessed_others = session.get('guessed_others', [])
    guessed_artists = session.get('guessed_artists', [])

    plot_url = None
    if guessed_listeners:
        # Prepare DataFrame
        data = pd.DataFrame({
            'Guess': [f"Guess {i+1}" for i in range(len(guessed_listeners))] * 2,
            'Monthly Listeners': guessed_listeners + guessed_others,
            'Artist': [artist for artist, _ in guessed_artists] + [other for _, other in guessed_artists],
            'Category': ['Chosen Artist'] * len(guessed_listeners) + ['Other Artist'] * len(guessed_others)
        })

        # Set Seaborn dark theme
        sns.set_theme(style="darkgrid", rc={"axes.facecolor": "#282a36", "grid.color": "#44475a"})

        # Create bar chart
        plt.figure(figsize=(12, 6))
        ax = sns.barplot(
            x="Guess",
            y="Monthly Listeners",
            hue="Category",
            data=data,
            palette={"Chosen Artist": "#50fa7b", "Other Artist": "#ff79c6"}
        )

        # Add text inside bars (artist names) & on top (listener counts)
        for bar, artist, value in zip(ax.patches, data["Artist"], data["Monthly Listeners"]):
            height = bar.get_height()
            
            # Artist name inside the bar
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height - (height * 0.08),  # Slightly lower inside the bar
                artist,
                ha='center',
                va='top',
                fontsize=10,
                color='black' if height > 5_000_000 else 'white'  # Adjust text color for contrast
            )
            
            # Listener count closer to bar top
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + (height * 0.007),  # Moves number slightly down for better alignment
                f"{value:,}",
                ha='center',
                va='bottom',
                fontsize=11,
                color='white'
            )

        # Styling
        plt.xticks(rotation=45, color="white")
        plt.yticks(color="white")
        plt.xlabel("Guess Number", color="white")
        plt.ylabel("Monthly Listeners", color="white")
        plt.title("Game Progression", color="white")
        plt.legend(title="Artist", labelcolor="white", facecolor="#282a36")

        # Convert plot to base64
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches="tight", facecolor="#282a36")
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()

    session.clear()

    return render_template('game_over.html', score=score, plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)