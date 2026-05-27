import sqlite3
import hashlib
import secrets
import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from cryptography.fernet import Fernet

# -------------------------------------------------------------------
# Configuração geral
# -------------------------------------------------------------------

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

CHAVE_FERNET = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='
fernet = Fernet(CHAVE_FERNET)

DB_PATH = os.path.join(os.path.dirname(__file__), 'mensagens.db')
SESSAO_EXPIRA_MIN = 30  # tokens expiram após 30 minutos de inatividade

# token -> {'username': str, 'criado_em': datetime}
sessoes = {}


# -------------------------------------------------------------------
# Banco de dados
# -------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            senha_hash  TEXT NOT NULL,
            papel       TEXT NOT NULL DEFAULT 'user'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS mensagens (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            remetente        TEXT NOT NULL,
            destinatario     TEXT NOT NULL,
            conteudo_cifrado BLOB NOT NULL,
            timestamp        TEXT NOT NULL,
            lida             INTEGER DEFAULT 0
        )
    ''')

    usuarios_padrao = [
        ('admin', 'admin123', 'admin'),
        ('alice', 'alice123', 'user'),
        ('bob',   'bob123',   'user'),
    ]
    for username, senha, papel in usuarios_padrao:
        h = hashlib.sha256(senha.encode()).hexdigest()
        try:
            c.execute(
                'INSERT INTO usuarios (username, senha_hash, papel) VALUES (?, ?, ?)',
                (username, h, papel)
            )
            log.info(f'Usuário padrão criado: {username} ({papel})')
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Helpers de sessão
# -------------------------------------------------------------------

def _limpar_sessoes_expiradas():
    expiradas = [
        t for t, dados in sessoes.items()
        if datetime.utcnow() - dados['criado_em'] > timedelta(minutes=SESSAO_EXPIRA_MIN)
    ]
    for t in expiradas:
        log.info(f'Sessão expirada removida: usuário={sessoes[t]["username"]}')
        del sessoes[t]


def usuario_da_sessao(token):
    _limpar_sessoes_expiradas()
    entrada = sessoes.get(token)
    if not entrada:
        return None
    # Renova o tempo a cada requisição (sliding window)
    entrada['criado_em'] = datetime.utcnow()
    return entrada['username']


def get_papel(username):
    conn = get_db()
    row = conn.execute('SELECT papel FROM usuarios WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row['papel'] if row else None


def _token_do_header():
    return request.headers.get('Authorization', '').replace('Bearer ', '').strip()


# -------------------------------------------------------------------
# Autenticação
# -------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    ip = request.remote_addr
    dados = request.get_json(silent=True) or {}
    username = dados.get('username', '').strip()
    senha    = dados.get('senha', '')

    if not username or not senha:
        log.warning(f'Tentativa de login sem credenciais completas | IP={ip}')
        return jsonify({'erro': 'Username e senha são obrigatórios'}), 400

    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    conn = get_db()
    row = conn.execute(
        'SELECT * FROM usuarios WHERE username = ? AND senha_hash = ?',
        (username, senha_hash)
    ).fetchone()
    conn.close()

    if not row:
        log.warning(f'Falha de login para "{username}" | IP={ip}')
        return jsonify({'erro': 'Credenciais inválidas'}), 401

    token = secrets.token_hex(32)
    sessoes[token] = {'username': username, 'criado_em': datetime.utcnow()}
    log.info(f'Login bem-sucedido: {username} ({row["papel"]}) | IP={ip}')

    return jsonify({
        'token': token,
        'papel': row['papel'],
        'expira_em_min': SESSAO_EXPIRA_MIN,
        'mensagem': f'Bem-vindo, {username}!'
    })


@app.route('/logout', methods=['POST'])
def logout():
    token = _token_do_header()
    username = usuario_da_sessao(token)
    if username:
        del sessoes[token]
        log.info(f'Logout: {username}')
    return jsonify({'mensagem': 'Sessão encerrada'})


# -------------------------------------------------------------------
# Mensagens
# -------------------------------------------------------------------

@app.route('/mensagem/enviar', methods=['POST'])
def enviar_mensagem():
    token     = _token_do_header()
    remetente = usuario_da_sessao(token)
    if not remetente:
        return jsonify({'erro': 'Não autenticado ou sessão expirada'}), 401

    dados        = request.get_json(silent=True) or {}
    destinatario = dados.get('destinatario', '').strip()
    conteudo     = dados.get('conteudo', '').strip()

    if not destinatario or not conteudo:
        return jsonify({'erro': 'Destinatário e conteúdo são obrigatórios'}), 400

    conn = get_db()
    dest_row = conn.execute(
        'SELECT username FROM usuarios WHERE username = ?', (destinatario,)
    ).fetchone()

    if not dest_row:
        conn.close()
        return jsonify({'erro': f'Usuário "{destinatario}" não encontrado'}), 404

    conteudo_cifrado = fernet.encrypt(conteudo.encode())
    timestamp = datetime.utcnow().isoformat()

    conn.execute(
        'INSERT INTO mensagens (remetente, destinatario, conteudo_cifrado, timestamp, lida) VALUES (?, ?, ?, ?, 0)',
        (remetente, destinatario, conteudo_cifrado, timestamp)
    )
    conn.commit()
    conn.close()

    log.info(f'Mensagem enviada: {remetente} -> {destinatario}')
    return jsonify({
        'mensagem': 'Mensagem enviada com sucesso',
        'timestamp': timestamp,
        'bytes_cifrados': len(conteudo_cifrado)
    })


@app.route('/mensagem/caixa-de-entrada', methods=['GET'])
def caixa_de_entrada():
    token    = _token_do_header()
    username = usuario_da_sessao(token)
    if not username:
        return jsonify({'erro': 'Não autenticado ou sessão expirada'}), 401

    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM mensagens WHERE destinatario = ? ORDER BY timestamp DESC',
        (username,)
    ).fetchall()

    resultado = []
    for row in rows:
        conteudo = fernet.decrypt(row['conteudo_cifrado']).decode()
        conn.execute('UPDATE mensagens SET lida = 1 WHERE id = ?', (row['id'],))
        resultado.append({
            'id':        row['id'],
            'remetente': row['remetente'],
            'conteudo':  conteudo,
            'timestamp': row['timestamp'],
            'lida':      row['lida'],
        })

    conn.commit()
    conn.close()
    log.info(f'Caixa de entrada acessada por: {username} ({len(resultado)} mensagem(ns))')
    return jsonify({'mensagens': resultado, 'total': len(resultado)})


@app.route('/mensagem/enviadas', methods=['GET'])
def mensagens_enviadas():
    token    = _token_do_header()
    username = usuario_da_sessao(token)
    if not username:
        return jsonify({'erro': 'Não autenticado ou sessão expirada'}), 401

    conn = get_db()
    rows = conn.execute(
        'SELECT id, destinatario, timestamp, lida FROM mensagens WHERE remetente = ? ORDER BY timestamp DESC',
        (username,)
    ).fetchall()
    conn.close()

    resultado = [
        {
            'id':          row['id'],
            'destinatario': row['destinatario'],
            'timestamp':   row['timestamp'],
            'lida':        bool(row['lida']),
        }
        for row in rows
    ]
    return jsonify({'enviadas': resultado, 'total': len(resultado)})


@app.route('/mensagem/todas', methods=['GET'])
def todas_mensagens():
    token    = _token_do_header()
    username = usuario_da_sessao(token)
    if not username:
        return jsonify({'erro': 'Não autenticado ou sessão expirada'}), 401

    if get_papel(username) != 'admin':
        log.warning(f'Acesso negado a /mensagem/todas: usuário={username}')
        return jsonify({'erro': 'Acesso negado — somente administradores'}), 403

    conn = get_db()
    rows = conn.execute('SELECT * FROM mensagens ORDER BY timestamp DESC').fetchall()
    conn.close()

    resultado = []
    for row in rows:
        conteudo = fernet.decrypt(row['conteudo_cifrado']).decode()
        resultado.append({
            'id':          row['id'],
            'remetente':   row['remetente'],
            'destinatario': row['destinatario'],
            'conteudo':    conteudo,
            'timestamp':   row['timestamp'],
            'lida':        bool(row['lida']),
        })

    log.info(f'Admin "{username}" listou todas as mensagens ({len(resultado)})')
    return jsonify({'mensagens': resultado, 'total': len(resultado)})


# -------------------------------------------------------------------
# Gestão de usuários (admin)
# -------------------------------------------------------------------

@app.route('/usuario/cadastrar', methods=['POST'])
def cadastrar_usuario():
    token    = _token_do_header()
    solicitante = usuario_da_sessao(token)
    if not solicitante:
        return jsonify({'erro': 'Não autenticado ou sessão expirada'}), 401

    if get_papel(solicitante) != 'admin':
        log.warning(f'Tentativa não autorizada de cadastro por: {solicitante}')
        return jsonify({'erro': 'Acesso negado — somente administradores podem cadastrar usuários'}), 403

    dados    = request.get_json(silent=True) or {}
    novo_usr = dados.get('username', '').strip()
    senha    = dados.get('senha', '')
    papel    = dados.get('papel', 'user').strip().lower()

    if not novo_usr or not senha:
        return jsonify({'erro': 'Username e senha são obrigatórios'}), 400

    if len(novo_usr) < 3:
        return jsonify({'erro': 'Username deve ter pelo menos 3 caracteres'}), 400

    if len(senha) < 6:
        return jsonify({'erro': 'Senha deve ter pelo menos 6 caracteres'}), 400

    if papel not in ('user', 'admin'):
        return jsonify({'erro': 'Papel inválido — use "user" ou "admin"'}), 400

    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO usuarios (username, senha_hash, papel) VALUES (?, ?, ?)',
            (novo_usr, senha_hash, papel)
        )
        conn.commit()
        conn.close()
        log.info(f'Novo usuário cadastrado por {solicitante}: {novo_usr} ({papel})')
        return jsonify({'mensagem': f'Usuário "{novo_usr}" cadastrado com sucesso'})
    except sqlite3.IntegrityError:
        return jsonify({'erro': f'Username "{novo_usr}" já existe'}), 409


@app.route('/usuario/listar', methods=['GET'])
def listar_usuarios():
    token    = _token_do_header()
    username = usuario_da_sessao(token)
    if not username:
        return jsonify({'erro': 'Não autenticado ou sessão expirada'}), 401

    if get_papel(username) != 'admin':
        return jsonify({'erro': 'Acesso negado — somente administradores'}), 403

    conn = get_db()
    rows = conn.execute('SELECT username, papel FROM usuarios ORDER BY papel, username').fetchall()
    conn.close()

    ativos = {dados['username'] for dados in sessoes.values()}
    usuarios = [
        {
            'username': r['username'],
            'papel':    r['papel'],
            'sessao_ativa': r['username'] in ativos,
        }
        for r in rows
    ]
    return jsonify({'usuarios': usuarios, 'sessoes_abertas': len(ativos)})


# -------------------------------------------------------------------
# Inicialização
# -------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    log.info('Servidor iniciado em http://0.0.0.0:5000')
    log.info(f'Sessões expiram após {SESSAO_EXPIRA_MIN} minutos de inatividade')
    app.run(host='0.0.0.0', port=5000, debug=False)
