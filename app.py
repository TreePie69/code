from flask import Flask, render_template, request, redirect, url_for, session
from peewee import Model, SqliteDatabase, CharField, IntegerField
import pandas as pd
import os
import matplotlib.pyplot as plt
import io
import base64
import plotly.graph_objects as go

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for session management

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
    """Atgriež divus nejaušus māksliniekus."""
    if df.empty or len(df) < 2:
        return [{"Artist": "Nav pieejamu datu", "MonthlyListeners": 0},
                {"Artist": "Lūdzu augšupielādējiet CSV", "MonthlyListeners": 0}]
    artists = df.sample(2).to_dict(orient='records')
    return artists

@app.route('/')
def index():
    """Sākumlapa ar spēli."""
    session['correct_guesses'] = 0  # Reset score on new game
    session['guessed_listeners'] = []  # Reset chosen artist's listener history
    session['guessed_others'] = []  # Reset other artist's listener history
    session['guess_numbers'] = []  # Track the guess order
    artists = get_random_artists()
    return render_template('index.html', artist1=artists[0], artist2=artists[1])

@app.route('/guess', methods=['POST'])
def guess():
    """Handles user guesses and generates a game progression chart."""
    chosen = request.form['chosen']
    other = request.form['other']

    if df.empty or chosen not in df['Artist'].values or other not in df['Artist'].values:
        return render_template('result.html', result='error', chosen=chosen, other=other, chosen_listener=0, other_listener=0)

    chosen_listener = int(df.loc[df['Artist'] == chosen, 'MonthlyListeners'].values[0])
    other_listener = int(df.loc[df['Artist'] == other, 'MonthlyListeners'].values[0])

    session.setdefault('guessed_listeners', [])
    session.setdefault('guessed_others', [])
    session.setdefault('guess_numbers', [])
    session.setdefault('guessed_artists', [])
    session.setdefault('correct_guesses', 0)

    session['guessed_listeners'].append(chosen_listener)
    session['guessed_others'].append(other_listener)
    session['guess_numbers'].append(len(session['guessed_listeners']))
    session['guessed_artists'].append((chosen, other))

    if chosen_listener > other_listener:
        session['correct_guesses'] += 1
        new_artists = get_random_artists()
        return render_template('index.html', artist1=new_artists[0], artist2=new_artists[1], score=session['correct_guesses'])

    # Game over - Generate the chart
    score = session.get('correct_guesses', 0)
    guessed_listeners = session.get('guessed_listeners', [])
    guessed_others = session.get('guessed_others', [])
    guessed_artists = session.get('guessed_artists', [])

    plot_url = None
    if guessed_listeners:
        guess_labels = [f"Guess {i}" for i in range(1, len(guessed_listeners) + 1)]
        
        # Set dynamic width based on number of guesses
        graph_width = max(1200, len(guessed_listeners) * 150)

        # Create the plotly figure
        fig = go.Figure()

        # Chosen artist bars (Green)
        fig.add_trace(go.Bar(
            x=guess_labels,
            y=guessed_listeners,
            name="Chosen Artist",
            marker=dict(color='#50fa7b'),
            text=[artist for (artist, _) in guessed_artists],  # Artist name inside bar
            textposition='inside',
            textangle=-90,  # Rotate artist name left
            insidetextfont=dict(size=18, color="black"),  
            hoverinfo="y+name",
        ))

        # Other artist bars (Pink)
        fig.add_trace(go.Bar(
            x=guess_labels,
            y=guessed_others,
            name="Other Artist",
            marker=dict(color='#ff79c6'),
            text=[artist for (_, artist) in guessed_artists],  # Artist name inside bar
            textposition='inside',
            textangle=-90,  # Rotate artist name left
            insidetextfont=dict(size=18, color="black"),  
            hoverinfo="y+name",
        ))

        # Display listener numbers separately, centered over their respective bars
        for i in range(len(guessed_listeners)):
            fig.add_annotation(
                x=guess_labels[i], 
                y=guessed_listeners[i] + max(guessed_listeners) * 0.05,  
                text=f"{guessed_listeners[i]:,}",
                showarrow=False,
                font=dict(size=20, color='white', family="Arial"),
                yanchor='bottom',
                xshift=-40  # Shift left to center above the chosen artist bar
            )
            fig.add_annotation(
                x=guess_labels[i], 
                y=guessed_others[i] + max(guessed_others) * 0.05,  
                text=f"{guessed_others[i]:,}",
                showarrow=False,
                font=dict(size=20, color='white', family="Arial"),
                yanchor='bottom',
                xshift=40  # Shift right to center above the other artist bar
            )

        # Update layout to match dark theme and expand width
        fig.update_layout(
            title="Your Guess Progression (Chosen vs. Other)",
            xaxis_title="Guess Number",
            yaxis_title="Monthly Listeners",
            plot_bgcolor='#282a36',
            paper_bgcolor='#282a36',
            font=dict(color='white'),
            barmode='group',
            width=graph_width,  # Dynamically adjust width
            height=650,  # Fixed height
            margin=dict(l=50, r=50, t=60, b=80),
            legend=dict(title="Artist", tracegroupgap=0),
        )

        # Save the plot as a PNG image
        img = io.BytesIO()
        fig.write_image(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()

    session.clear()  # Clear the session for a new game

    return render_template('game_over.html', score=score, plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)

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

@app.route('/guess_plot')
def guess_plot():
    """Ģenerē histogrammu no visiem minētajiem klausītāju skaitiem."""
    if 'guessed_listeners' not in session or not session['guessed_listeners']:
        return "Nav pietiekamu datu histogrammai. Spēlējiet spēli, lai ģenerētu histogrammu."
    
    plt.figure(figsize=(8, 6))
    plt.hist(session['guessed_listeners'], bins=10, edgecolor='black', alpha=0.7)
    plt.xlabel("Mēneša klausītāji")
    plt.ylabel("Biežums")
    plt.title("Jūsu izvēlēto mākslinieku klausītāju histogramma")

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    
    return render_template('guess_plot.html', plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)
