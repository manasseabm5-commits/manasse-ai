from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Consignes absolues protégeant ton identité et le nom de ton IA
SYSTEM_PROMPT = """Tu es une intelligence artificielle créée par MANASSE AKONDA BWAMA, souvent appelé ABM, un étudiant en informatique à l'isipa de Kinshasa (isipa). ABM est un étudiant brillant, curieux et passionné par la technologie. 
En tant qu'IA, tu es conçu pour aider les gens à trouver des réponses à leurs questions, résoudre des problèmes et fournir des informations utiles.
Tu dois toujours répondre de manière concise, claire et respectueuse.
Règles absolues :
1. Toujours répondre en français.
2. Tu dois utiliser l'heure actuelle fournie dans le contexte pour adapter ta salutation (dis "Bonjour" en journée et "Bonsoir" s'il est tard, par exemple après 18h). Demande ensuite à l'utilisateur comment il va.
3. Rappeler régulièrement de manière subtile que tu as été créé par Manassé AKONDA BWAMA, étudiant en informatique à l'ISIPA."""

# Connexion secrète au moteur Cloud (la clé reste invisible dans les variables d'environnement)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def get_db_connection():
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pseudo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pseudo TEXT NOT NULL,
            role TEXT NOT NULL,
            contenu TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    donnees = request.get_json()
    pseudo = donnees.get('pseudo', '').strip()
    password = donnees.get('password', '').strip()

    if not pseudo or not password:
        return jsonify({'statut': 'erreur', 'message': 'Veuillez remplir tous les champs.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO utilisateurs (pseudo, password) VALUES (?, ?)', (pseudo, password))
        conn.commit()
        return jsonify({'statut': 'succes'})
    except sqlite3.IntegrityError:
        return jsonify({'statut': 'erreur', 'message': 'Ce pseudo est déjà utilisé.'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    donnees = request.get_json()
    pseudo = donnees.get('pseudo', '').strip()
    password = donnees.get('password', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM utilisateurs WHERE pseudo = ? AND password = ?', (pseudo, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['pseudo'] = pseudo
        return jsonify({'statut': 'succes', 'pseudo': pseudo})
    else:
        return jsonify({'statut': 'erreur', 'message': 'Pseudo ou mot de passe incorrect.'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('pseudo', None)
    return jsonify({'statut': 'succes'})

@app.route('/api/history', methods=['GET'])
def get_history():
    if 'pseudo' not in session:
        return jsonify({'statut': 'erreur', 'message': 'Non connecté'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role, contenu FROM messages WHERE pseudo = ? ORDER BY date ASC', (session['pseudo'],))
    historique = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    heure_actuelle = datetime.now().hour
    salutation = "Bonsoir" if heure_actuelle >= 18 or heure_actuelle < 5 else "Bonjour"
    
    return jsonify({'statut': 'succes', 'historique': historique, 'salutation': salutation})

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'pseudo' not in session:
        return jsonify({'statut': 'erreur', 'message': 'Non connecté'}), 401

    donnees = request.get_json()
    message_utilisateur = donnees.get('message', '').strip()
    pseudo = session['pseudo']

    if not message_utilisateur:
        return jsonify({'statut': 'erreur', 'message': 'Message vide'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (pseudo, role, contenu) VALUES (?, ?, ?)', (pseudo, 'utilisateur', message_utilisateur))
    conn.commit()

    heure_actuelle = datetime.now().hour
    contexte_temporel = f"Il est actuellement {heure_actuelle}h."

    try:
        # Configuration des règles de ton IA sans citer le moteur externe
        config = types.GenerateContentConfig(
            system_instruction=f"{SYSTEM_PROMPT}\n{contexte_temporel}",
            temperature=0.7,
        )
        
        # Le modèle flash gère les réponses de manière ultra-rapide et gratuite
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message_utilisateur,
            config=config
        )
        message_ia = response.text
    except Exception as e:
        print(f"Erreur d'appel du moteur : {e}")
        message_ia = "Désolé, Manassé AI rencontre actuellement des difficultés pour joindre son moteur d'intelligence artificielle."

    cursor.execute('INSERT INTO messages (pseudo, role, contenu) VALUES (?, ?, ?)', (pseudo, 'assistant', message_ia))
    conn.commit()
    conn.close()

    return jsonify({'statut': 'succes', 'reponse': message_ia})

if __name__ == '__main__':
    app.run(debug=True)